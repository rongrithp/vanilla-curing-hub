# แผนภาพสถาปัตยกรรมข้อมูลและการไหลของระบบ (End-to-End Data Pipeline & Architecture Flow)
## ตู้บ่มวานิลลาอัตโนมัติ (Automated Vanilla Curing Hub - 5kg Prototype)

เอกสารฉบับนี้อธิบายทิศทางการไหลของข้อมูล (Data Flow) และการแปลงสภาพข้อมูล (Data Transformation) ตั้งแต่ระดับเซนเซอร์ภายในตู้บ่ม การติดตามถาดด้วย QR Code และเครื่องชั่งดิจิทัลภายนอก ฐานข้อมูลคลังจัดเก็บ (Database Ledger) จนถึงเอนจินปรับแต่งสูตรการบ่มแบบ Closed-Loop (Sensory Optimization Engine)

---

## 1. ผังการไหลของข้อมูลภาพรวมระบบ (End-to-End System Architecture Flowchart)

```mermaid
%%{init: { 'themeVariables': { 'fontSize': '24px', 'fontFamily': 'sans-serif', 'nodePadding': 20 } } }%%
graph TD
    classDef default font-size:22px,font-weight:bold,stroke-width:2px;

    %% Layer 1: Hardware Chamber Pod
    subgraph Hardware_Layer["1. Hardware Chamber Layer (ESP32 Pod)"]
        SHT31["SHT31 Sensor<br/>(Temp & RH)"] -->|I2C Read| ESP32["ESP32 Controller<br/>(FSM Loop)"]
        ESP32 -->|Tetens Formula| VPD_Calc["VPD Computation<br/>(kPa)"]
        VPD_Calc -->|Closed-Loop Feedback| Actuators["Actuators<br/>(PTC Heater, Fan, Vent)"]
        ESP32 -->|BLE / Serial Stream| Telemetry_Stream["Telemetry Stream<br/>(JSON)"]
    end

    %% Layer 2: Mobile & Edge Traceability
    subgraph Traceability_Layer["2. Manual & Edge Traceability Layer (Mobile App)"]
        Scale["External Scale<br/>(0.1g / 1g)"] -->|Weigh Tray| User_Action["User Tray<br/>Inspection"]
        QR_Code["Tray QR Code Tag"] -->|Scan via Smartphone| Mobile_App["Smartphone<br/>Client App"]
        User_Action --> Mobile_App
        Mobile_App -->|Macro Snapshot| Edge_AI["On-Device Edge AI<br/>(OpenCV + Gemini Nano)"]
        Edge_AI -->|Brown Ratio % & Mold Check| Inspection_Payload["Inspection Record<br/>Payload"]
    end

    %% Layer 3: Data Ledger & Storage
    subgraph Storage_Layer["3. Data Ledger & Storage Layer"]
        Telemetry_Stream -->|Time-Series Insert| SQLite_DB[("SQLite Database<br/>(curing_hub.db)")]
        Inspection_Payload -->|Record Insert| SQLite_DB
        SQLite_DB -->|Export Traceability| JSON_Schema["batch_schema.json"]
    end

    %% Layer 4: Closed-Loop Optimization
    subgraph Optimization_Layer["4. Closed-Loop Recipe Optimization Engine"]
        Finished_Pods["Cured Vanilla Pods"] -->|HPLC Analysis| HPLC_Data["% Vanillin Content"]
        Finished_Pods -->|Sensory Cupping| Sensory_Data["Sensory Radar Scores<br/>(Sweetness, Creamy, Floral, Woody)"]
        HPLC_Data --> Opt_Engine["sensory_optimization.py"]
        Sensory_Data --> Opt_Engine
        Opt_Engine -->|Closed-Loop Feedback| Optimized_Recipe["Optimized Recipe<br/>(Temp, VPD, Time)"]
        Optimized_Recipe -->|Apply Next Batch| ESP32
    end
```

---

## 2. ลำดับการทำงานของข้อมูลแบบละเอียดยิบ (End-to-End Sequence Diagram)

```mermaid
%%{init: { 'sequence': { 'actorFontSize': 24, 'messageFontSize': 22, 'noteFontSize': 22, 'labelFontSize': 22, 'boxTextMargin': 15, 'noteMargin': 15 }, 'themeVariables': { 'fontSize': '24px', 'fontFamily': 'sans-serif' } } }%%
sequenceDiagram
    autonumber
    actor Operator as ผู้ใช้งาน<br/>(Operator)
    participant Scale as เครื่องชั่งดิจิทัล<br/>ภายนอก
    participant Phone as สมาร์ทโฟน /<br/>Mobile App
    participant EdgeAI as On-device<br/>Edge AI
    participant ESP32 as ESP32 Chamber<br/>Controller
    participant DB as SQLite DB<br/>(curing_hub.db)
    participant OptEngine as Sensory Optimization<br/>Engine

    rect rgb(240, 248, 255)
        note over ESP32, DB: 1. Hardware Closed-Loop Control & Telemetry Stream
        ESP32->>ESP32: อ่านค่า SHT31 (Temp, RH)<br/>และคำนวณ VPD (Tetens Equation)
        ESP32->>ESP32: ปรับตำแหน่ง Servo Vent (Deadband 0.9-1.1 kPa)<br/>และควบคุม PTC Heater
        ESP32->>DB: บันทึก Time-Series Telemetry<br/>(ทุก 5 วินาที)
    end

    rect rgb(255, 250, 240)
        note over Operator, EdgeAI: 2. Tray Inspection & Weight Tracking (External Scale + QR)
        Operator->>Scale: ชั่งน้ำหนักถาดฝักวานิลลาสด (g)
        Operator->>Phone: สแกน QR Code หน้าถาด<br/>+ ถ่ายภาพมาโคร
        Phone->>EdgeAI: ส่งภาพวิเคราะห์ด้วย OpenCV (Brown Ratio)<br/>+ Gemini Nano (Mold Check)
        EdgeAI-->>Phone: คืนค่า Brown Ratio %<br/>และสถานะสปอร์เชื้อรา
        Phone->>DB: บันทึกข้อมูลถาด (น้ำหนัก Mt,<br/>Brown Ratio %, URIs ภาพถ่าย)
    end

    rect rgb(245, 255, 250)
        note over DB, OptEngine: 3. Recipe Optimization & Quality Feedback Loop
        DB->>DB: คำนวณอัตราส่วนมวลคงเหลือ<br/>(Mass Ratio = Mt / Initial_Mass)
        alt มวลคงเหลือ <= 27.0% (Exit Condition)
            DB->>ESP32: จบ Active Lifecycle<br/>(เปลี่ยนสถานะเป็น READY_FOR_NEXT_BATCH)
            Operator->>OptEngine: ป้อนผล HPLC (% Vanillin)<br/>& Sensory Radar Scores
            OptEngine->>OptEngine: คำนวณปรับแต่งสูตรการบ่ม<br/>(Sweating T/Duration, Drying T/VPD)
            OptEngine->>DB: บันทึกและส่งออก batch_schema.json
            OptEngine-->>ESP32: อัปเดต Recipe ใหม่สำหรับแบทช์ถัดไป
        end
    end
```

---

## 3. รายละเอียดการแปลงสภาพข้อมูลในแต่ละลำดับชั้น (Data Transformation Pipeline Details)

### 3.1 Hardware Layer (In-Chamber Telemetry Transformation)
- **การป้อนเข้า (Input):** ค่าอนาล็อก/ดิจิทัลจากเซนเซอร์ SHT31 (อุณหภูมิ $T_{\text{air}}$ และ ความชื้นสัมพัทธ์ $\text{RH}_{\text{air}}$) ผ่าน I2C
- **สมการประมวลผล (Transformation):** สมการ Tetens Equation คำนวณค่าความดันไอน้ำส่วนขาด (VPD):
  $$\text{VPD} = 0.61078 \times \exp\left(\frac{17.27 \times T_{\text{air}}}{T_{\text{air}} + 237.3}\right) \times \left(1 - \frac{\text{RH}_{\text{air}}}{100}\right) \quad [\text{kPa}]$$
- **ผลลัพธ์ (Output):** คำสั่งปรับระดับองศา Servo Vent ($\pm 10\%$) ตามช่วง Hysteresis Deadband $[0.9, 1.1]\text{ kPa}$ และ JSON Telemetry Stream ออกทาง BLE/Serial

### 3.2 Manual & Edge Traceability Layer (Tray Tracking via QR)
- **การป้อนเข้า (Input):** ภาพถ่ายมาโครประจำถาด + ค่าน้ำหนักถาดสดจากเครื่องชั่งดิจิทัลภายนอก + รหัส QR Code ประจำถาด
- **สมการประมวลผล (Transformation):**
  - OpenCV HSV Color Segmentation หาค่า `brown_ratio` (%)
  - Gemini Nano Edge AI ตรวจสอบ `mold_detected` (Boolean)
  - คำนวณเปอร์เซ็นต์มวลคงเหลือ: $\text{Mass Ratio (\%)} = \left(\frac{M_{\text{current}}}{M_{\text{initial}}}\right) \times 100$
- **ผลลัพธ์ (Output):** โครงสร้างข้อมูล `InspectionPayload` บันทึกลงตาราง `vision_inspections` และ `sensor_telemetry`

### 3.3 Data Ledger & Storage Layer
- **การป้อนเข้า (Input):** ข้อมูลเซนเซอร์เรียลไทม์ และข้อมูลสแกนถาดรายวัน
- **สมการประมวลผล (Transformation):** จัดรูปแบบเป็น Schema มาตรฐานตาม [batch_schema.json](file:///g:/My%20Drive/06.%20vanilla-curing-hub/batch_schema.json)
- **ผลลัพธ์ (Output):** ฐานข้อมูล SQLite [curing_hub.db](file:///g:/My%20Drive/06.%20vanilla-curing-hub/curing_hub.db) (WAL Mode) และไฟล์ส่งออก JSON

### 3.4 Closed-Loop Optimization Engine
- **การป้อนเข้า (Input):** ผลตรวจทางแล็บ HPLC (% Vanillin) และผลทดลองชิม Sensory Cupping Radar Score (`sweetness`, `creamy`, `floral`, `woody`, `defect_off_flavor`)
- **สมการประมวลผล (Transformation):** ฟังก์ชัน `compute_optimized_recipe()` ใน [sensory_optimization.py](file:///g:/My%20Drive/06.%20vanilla-curing-hub/sensory_optimization.py) คำนวณปรับแต่งอุณหภูมิ ระยะเวลาบ่ม และเป้าหมาย VPD
- **ผลลัพธ์ (Output):** ค่า Recipe Parameters ใหม่ที่ได้รับการ Optimize เพื่อส่งต่อให้ ESP32 Controller ใช้ในการบ่มแบทช์ถัดไป
