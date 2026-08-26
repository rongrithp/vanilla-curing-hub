/**
 * @file esp32_curing_controller.ino
 * @brief Automated Vanilla Curing Hub - ESP32 Firmware Controller
 * @details Implements non-blocking sensor polling, Tetens VPD computation,
 *          decoupled actuator control loop, local display HMI, and hardware safety watchdog.
 *
 * HOW TO RUN SIMULATION IN WOKWI:
 * 1. VS Code: Install "Wokwi Simulator" extension -> Open project folder -> Press F1 -> Select "Wokwi: Start Simulator"
 * 2. Web Browser: Go to https://wokwi.com -> Upload esp32_curing_controller.ino & diagram.json
 */

#include <Arduino.h>
#include <Wire.h>
#include <math.h>

// Option libraries for display and sensors
#include <Adafruit_SHT31.h>
#include <Adafruit_SSD1306.h>
#include <HX711.h>

// Pin Definitions for ESP32 & Wokwi Simulator
#define SHT31_I2C_ADDR      0x44
#define OLED_I2C_ADDR       0x3C
#define OLED_SCREEN_WIDTH   128
#define OLED_SCREEN_HEIGHT  64

#define PIN_HX711_DOUT      16
#define PIN_HX711_SCK       17

#define PIN_RELAY_HEATER    19  // Wokwi Red LED (PTC Heater SSR)
#define PIN_RELAY_FAN       23  // Wokwi Green LED (Circulating Fan)
#define PIN_SERVO_VENT      18  // Wokwi Servo Motor (Exhaust Vent)
#define PIN_STATUS_LED      2   // ESP32 Onboard Status LED

// Safety & Target Thresholds
#define HARD_TEMP_CUTOFF    58.0f // °C Emergency cutoff threshold
#define VPD_DEADBAND_MIN    0.90f // kPa (Minimum acceptable VPD in Stage 2)
#define VPD_DEADBAND_MAX    1.10f // kPa (Maximum acceptable VPD in Stage 2)
#define VPD_EVAL_INTERVAL   40000 // ms (40 seconds evaluation step)

// Curing Stage Enumeration
enum CuringStage {
    STAGE_0_PREKILL,
    STAGE_1_SWEATING,
    STAGE_2_SLOW_DRYING,
    STAGE_3_OFFCHAMBER,
    STAGE_EMERGENCY
};

// --------------------------------------------------------------------
// 1. VPD Calculator Module (Tetens Formula)
// --------------------------------------------------------------------
class VPDCalculator {
public:
    /**
     * Calculates Vapor Pressure Deficit (VPD) in kPa using Tetens Formula.
     * VPD = Es(T) * (1 - RH / 100)
     * where Es(T) = 0.61078 * exp((17.27 * T) / (T + 237.3))
     *
     * @param tempC Ambient Air Temperature in °C
     * @param rh Relative Humidity in % (0 - 100)
     * @return float VPD in kPa
     */
    static float calculateVPD(float tempC, float rh) {
        if (rh <= 0.0f || tempC < -20.0f) return 0.0f;
        
        // Saturation Vapor Pressure Es(T) in kPa
        float es = 0.61078f * expf((17.27f * tempC) / (tempC + 237.3f));
        // Actual Vapor Pressure Ea in kPa
        float ea = es * (rh / 100.0f);
        
        float vpd = es - ea;
        return (vpd > 0.0f) ? vpd : 0.0f;
    }
};

// --------------------------------------------------------------------
// 2. Sensors Module (SHT31 & HX711 Load Cell)
// --------------------------------------------------------------------
class SensorsModule {
private:
    Adafruit_SHT31 sht31;
    HX711 loadCell;
    
    float currentTempC = 0.0f;
    float currentRH = 0.0f;
    float currentMassG = 0.0f;
    float initialMassG = 5000.0f;
    bool sensorOk = false;
    unsigned long lastPollMs = 0;
    const unsigned long pollIntervalMs = 2000; // Poll sensors every 2 seconds

public:
    SensorsModule() {}

    bool begin() {
        Wire.begin();
        bool shtOk = sht31.begin(SHT31_I2C_ADDR);
        loadCell.begin(PIN_HX711_DOUT, PIN_HX711_SCK);
        
        // Default scale calibration factor for Load Cell
        loadCell.set_scale(420.0f);
        loadCell.tare();

        sensorOk = shtOk;
        return sensorOk;
    }

    void poll(unsigned long nowMs) {
        if (nowMs - lastPollMs >= pollIntervalMs) {
            lastPollMs = nowMs;

            float t = sht31.readTemperature();
            float h = sht31.readHumidity();

            if (!isnan(t) && !isnan(h) && t < 100.0f && h <= 100.0f) {
                currentTempC = t;
                currentRH = h;
                sensorOk = true;
            } else {
                sensorOk = false;
            }

            if (loadCell.is_ready()) {
                float reading = loadCell.get_units(3);
                currentMassG = (reading > 0.0f) ? reading : 0.0f;
            }
        }
    }

    float getTemperature() const { return currentTempC; }
    float getHumidity() const { return currentRH; }
    float getMassG() const { return currentMassG; }
    float getInitialMassG() const { return initialMassG; }
    float getMassRatio() const { return (initialMassG > 0) ? (currentMassG / initialMassG) : 1.0f; }
    bool isHealthy() const { return sensorOk; }
};

// --------------------------------------------------------------------
// 3. Decoupled Controller Module
// --------------------------------------------------------------------
class DecoupledController {
private:
    int ventPositionPercent = 0; // 0% (Fully Closed) to 100% (Fully Open)
    unsigned long lastVpdEvalMs = 0;

public:
    DecoupledController() {}

    void initPins() {
        pinMode(PIN_RELAY_HEATER, OUTPUT);
        pinMode(PIN_RELAY_FAN, OUTPUT);
        pinMode(PIN_SERVO_VENT, OUTPUT);
        pinMode(PIN_STATUS_LED, OUTPUT);
        
        digitalWrite(PIN_RELAY_HEATER, LOW);
        digitalWrite(PIN_RELAY_FAN, LOW);
        digitalWrite(PIN_STATUS_LED, LOW);
    }

    void update(
        CuringStage stage,
        float tempC,
        float rh,
        float vpd,
        float massRatio,
        bool sensorHealthy,
        unsigned long nowMs
    ) {
        // --- 1. HARD SAFETY WATCHDOG CUTOFF ---
        if (tempC >= HARD_TEMP_CUTOFF || !sensorHealthy || stage == STAGE_EMERGENCY) {
            digitalWrite(PIN_RELAY_HEATER, LOW); // Immediate Heater Cutoff
            digitalWrite(PIN_RELAY_FAN, HIGH);   // Max Airflow Purge
            ventPositionPercent = 100;           // Fully Open Exhaust Vent
            digitalWrite(PIN_STATUS_LED, (nowMs / 250) % 2 == 0 ? HIGH : LOW); // Rapid Hazard Blink
            return;
        }

        // --- 2. DECOUPLED CONTROL MATRIX ---
        switch (stage) {
            case STAGE_0_PREKILL:
            case STAGE_3_OFFCHAMBER:
                digitalWrite(PIN_RELAY_HEATER, LOW);
                digitalWrite(PIN_RELAY_FAN, LOW);
                ventPositionPercent = 0;
                digitalWrite(PIN_STATUS_LED, LOW);
                break;

            case STAGE_1_SWEATING:
                // Sweating Target Envelope: 45°C - 50°C, RH > 85%, Constant Fan, Vent Closed
                digitalWrite(PIN_RELAY_FAN, HIGH); // Constant Airflow Mode
                ventPositionPercent = 0;           // Vent closed to trap moisture

                if (tempC < 46.0f) {
                    digitalWrite(PIN_RELAY_HEATER, HIGH);
                } else if (tempC > 49.5f) {
                    digitalWrite(PIN_RELAY_HEATER, LOW);
                }
                digitalWrite(PIN_STATUS_LED, HIGH);
                break;

            case STAGE_2_SLOW_DRYING:
                // Slow Drying Envelope: 35°C - 38°C, VPD ~ 1.0 kPa
                digitalWrite(PIN_RELAY_FAN, HIGH); // Constant Airflow Mode

                // Dedicated PTC Thermal Control
                if (tempC < 35.5f) {
                    digitalWrite(PIN_RELAY_HEATER, HIGH);
                } else if (tempC > 37.5f) {
                    digitalWrite(PIN_RELAY_HEATER, LOW);
                }

                // Stepwise Exhaust Vent Modulation based on VPD (Evaluated every 40 sec)
                if (nowMs - lastVpdEvalMs >= VPD_EVAL_INTERVAL) {
                    lastVpdEvalMs = nowMs;

                    if (vpd < VPD_DEADBAND_MIN) {
                        // Air is too humid (VPD low) -> Open vent step to increase drying rate
                        ventPositionPercent = min(100, ventPositionPercent + 10);
                    } else if (vpd > VPD_DEADBAND_MAX) {
                        // Air is too dry (VPD high) -> Close vent step to retain moisture
                        ventPositionPercent = max(10, ventPositionPercent - 10);
                    }
                }
                digitalWrite(PIN_STATUS_LED, HIGH);
                break;

            default:
                digitalWrite(PIN_RELAY_HEATER, LOW);
                digitalWrite(PIN_RELAY_FAN, LOW);
                ventPositionPercent = 0;
                break;
        }
    }

    int getVentPosition() const { return ventPositionPercent; }
};

// --------------------------------------------------------------------
// 4. Local HMI Display Module
// --------------------------------------------------------------------
class LocalHMI {
private:
    Adafruit_SSD1306 display;
    bool oledOk = false;

public:
    LocalHMI() : display(OLED_SCREEN_WIDTH, OLED_SCREEN_HEIGHT, &Wire, -1) {}

    void begin() {
        if (display.begin(SSD1306_SWITCHCAPVCC, OLED_I2C_ADDR)) {
            oledOk = true;
            display.clearDisplay();
            display.setTextSize(1);
            display.setTextColor(SSD1306_WHITE);
            display.setCursor(0, 0);
            display.println("VANILLA CURING HUB");
            display.println("ESP32 Firmware Ready");
            display.display();
        }
    }

    void update(CuringStage stage, float tempC, float rh, float vpd, float massRatio, int ventPos) {
        if (!oledOk) return;

        display.clearDisplay();
        display.setCursor(0, 0);

        // Header Line
        display.print("STAGE: ");
        switch (stage) {
            case STAGE_0_PREKILL:     display.println("0 (PreKill)"); break;
            case STAGE_1_SWEATING:    display.println("1 (Sweat)"); break;
            case STAGE_2_SLOW_DRYING: display.println("2 (SlowDry)"); break;
            case STAGE_3_OFFCHAMBER:  display.println("3 (OffChamb)"); break;
            case STAGE_EMERGENCY:     display.println("EMERGENCY!"); break;
        }

        display.drawLine(0, 10, 128, 10, SSD1306_WHITE);

        // Telemetry Readouts
        display.setCursor(0, 14);
        display.printf("Temp:  %.1f C\n", tempC);
        display.printf("RH:    %.1f %%\n", rh);
        display.printf("VPD:   %.2f kPa\n", vpd);
        display.printf("Mass:  %.1f %%\n", massRatio * 100.0f);
        display.printf("Vent:  %d %%\n", ventPos);

        display.display();
    }
};

// --------------------------------------------------------------------
// Global Instantiations & Setup / Loop Execution
// --------------------------------------------------------------------
SensorsModule sensors;
DecoupledController controller;
LocalHMI hmi;

CuringStage currentStage = STAGE_1_SWEATING;

void setup() {
    Serial.begin(115200);
    Serial.println("\n--- Vanilla Curing Hub ESP32 Firmware Starting ---");

    controller.initPins();
    sensors.begin();
    hmi.begin();
}

void loop() {
    unsigned long now = millis();

    // 1. Non-blocking sensor polling
    sensors.poll(now);

    float t = sensors.getTemperature();
    float rh = sensors.getHumidity();
    float vpd = VPDCalculator::calculateVPD(t, rh);
    float massRatio = sensors.getMassRatio();
    bool healthy = sensors.isHealthy();

    // 2. Supervisory State Transition Evaluation
    if (t >= HARD_TEMP_CUTOFF || !healthy) {
        currentStage = STAGE_EMERGENCY;
    } else if (currentStage == STAGE_2_SLOW_DRYING && massRatio <= 0.27f) {
        currentStage = STAGE_3_OFFCHAMBER;
    }

    // 3. Update Decoupled Actuator Control Loop
    controller.update(currentStage, t, rh, vpd, massRatio, healthy, now);

    // 4. Update Local HMI Display
    hmi.update(currentStage, t, rh, vpd, massRatio, controller.getVentPosition());

    // 5. Serial Telemetry Stream (JSON format)
    static unsigned long lastSerialMs = 0;
    if (now - lastSerialMs >= 3000) {
        lastSerialMs = now;
        Serial.printf(
            "{\"stage\":%d, \"temp_c\":%.2f, \"rh_percent\":%.2f, \"vpd_kpa\":%.3f, \"mass_ratio\":%.3f, \"vent_pos\":%d, \"healthy\":%s}\n",
            (int)currentStage, t, rh, vpd, massRatio, controller.getVentPosition(), healthy ? "true" : "false"
        );
    }
}
