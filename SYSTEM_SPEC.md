# พิมพ์เขียวระบบ: ตู้บ่มวานิลลาอัตโนมัติ (AUTOMATED VANILLA CURING HUB - 5KG PROTOTYPE)

## 1. ขอบเขตและข้อจำกัดของระบบ (System Boundary & Scope)
- **ขนาดความจุเป้าหมาย (Target Capacity):** ฝักวานิลลาสด 5.0 kg (~250–350 ฝัก)
- **สถาปัตยกรรมทางกายภาพ (Physical Architecture):** 
  - ภายในตู้: ถาดตะแกรงซ้อนกัน 4 ชั้น (Mesh Trays ขนาด $30 \times 40\text{ cm}$, พื้นที่รวม $\ge 0.40\text{ m}^2$) พร้อมระบบหมุนเวียนลมร้อนแบบบังคับทิศทาง (Forced Convection)
  - กระบวนการตรวจสอบ (Smartphone-Centric Workflow): ใช้กล้องสมาร์ทโฟนถ่ายภาพมาโครประจำวัน (Daily Macro Snapshots) และสแกน QR Code บันทึกน้ำหนักถาดจากเครื่องชั่งดิจิทัลภายนอก ควบคู่กับการประมวลผลด้วย On-device Edge AI Inference
- **ขอบเขตกระบวนการอัตโนมัติ (Automated Chamber Scope):** ระบบตู้บ่มอัตโนมัติรองรับและควบคุมสภาพแวดล้อมตั้งแต่มวลสดเข้าตู้จนจบช่วง active chamber lifecycle ได้แก่ **STATE_0 (Pre-Kill & Sizing)**, **STATE_1 (Sweating)** ถึง **STATE_2 (Slow Drying)**
- **การย้ายกระบวนการบ่มนอกตู้ (Off-Chamber Conditioning):** ขั้นตอน **STATE_3 (Conditioning)** ถูก Offload ไปยังกล่องไม้ภายนอก (Manual/Off-chamber Storage) เพื่อคืนพื้นที่ภายในตู้ (Free up chamber throughput) ทำให้ตู้พร้อมเริ่มรองรับแบทช์ใหม่ได้ทันที
- **สิ่งที่ไม่ทำเด็ดขาด (Explicit Out of Scope):**
  - ไม่ติดตั้งกล้องภายในตู้ (ตัดปัญหากล้องขึ้นฝ้า ไอน้ำเกาะ และความร้อนสะสม)
  - ไม่ติดตั้งโหลดเซลล์ภายในตู้ (เปลี่ยนไปใช้เครื่องชั่งดิจิทัลภายนอกร่วมกับ QR Logging เพื่อแก้ปัญหา Sensor Drift จากความร้อนและความชื้นสะสม)

---

## 2. ทิศทางการไหลของข้อมูลและสถาปัตยกรรม (Topology & Data Flow)

```
+-------------------------------------------------------+
|              ESP32 Chamber Controller                 |
|  [Sensors: SHT31 Temp & RH]                           |
|  [Actuators: PTC Heater, Fan, Vent Relays]            |
|  [Firmware: FSM Loop, Closed-Loop VPD & Safety]       |
+-------------------------------------------------------+
                           ▲
                           │  Dual-Mode Connectivity
                           │  (BLE GATT / Wi-Fi REST & WebSockets)
                           ▼
+-------------------------------------------------------+
|          Smartphone Client & Edge AI Brain            |
|  [User Interface: Mobile Dashboard & Controls]        |
|  [Batch Logging: External Scale & QR Code Scan]       |
|  [Vision Engine: OpenCV (Color/Brown Ratio)]          |
|  [Edge AI Model: Gemini Nano / On-device Multimodal]  |
|  [Local Database: SQLite / IndexedDB + Cloud Sync]    |
+-------------------------------------------------------+
```

- **Chamber Controller & Actuators:** ESP32 Chamber Controller ทำหน้าที่รัน FSM Loop อ่านค่าเซนเซอร์ความชื้นและอุณหภูมิ (SHT31) คำนวณค่า VPD สัมพัทธ์ และสั่งการ Relays ควบคุมอุปกรณ์ทำความร้อน (PTC Heater), พัดลม (Fan) และช่องระบายอากาศ (Vent) พร้อมระบบ Hardware Watchdog
- **ระบบการเชื่อมต่อแบบสองโหมด (Dual-Mode Connectivity):**
  - **BLE (Bluetooth Low Energy GATT Service):** สำหรับการเชื่อมต่อ direct offline สั่งการและอ่านค่าเซนเซอร์ในระยะใกล้โดยไม่ต้องพึ่งพาเครือข่าย
  - **Wi-Fi (HTTP/WebSockets REST API):** สำหรับการสื่อสารแบบเรียลไทม์ภายในเครือข่ายท้องถิ่น (LAN)
- **แอปพลิเคชันฝั่งผู้ใช้และสมองกลประมวลผล (Client & Vision Brain):** Smartphone Application หรือ Web App ทำหน้าที่เป็น Dashboard แสดงผล บันทึกฐานข้อมูล และทำหน้าที่เป็น On-device Edge AI Engine:
  - **QR Code Batch & Tray Logging:** สแกน QR Code ประจำถาดเพื่อบันทึกค่าน้ำหนักจากเครื่องชั่งดิจิทัลภายนอก ($M_t \rightarrow 27\%$)
  - **OpenCV Engine:** คำนวณสัดส่วนสีผิวฝัก (Color / Brown Ratio) เพื่อประเมินความสุกและระดับการเปลี่ยนสี
- **รายละเอียดไดอะแกรมการไหลของข้อมูลแบบสมบูรณ์:** อ่านผังการทำงานและการแปลงสภาพข้อมูลละเอียดยิบได้ที่เอกสาร [DATA_PIPELINE.md](DATA_PIPELINE.md)

---

## 3. ตารางตรรกะการเปลี่ยนสถานะ (Deterministic State Machine)

| State ID | ชื่อเฟส (Phase Name) | สภาพแวดล้อมเป้าหมาย | เงื่อนไขการเปลี่ยนสถานะ (Exit Condition) | การสั่งการอุปกรณ์ (Actuator Behavior) |
|---|---|---|---|---|
| **STATE_0** | Pre-Kill & Sizing | อุณหภูมิห้องปกติ | ยืนยันขนาดฝักผ่านภาพถ่าย (กำหนดค่า $t_{kill}$) | Standby (ปิดทุกอย่าง) |
| **STATE_1** | Sweating (กระตุ้นเอนไซม์) | $45^\circ\text{C} - 50^\circ\text{C}$, $\text{RH} > 85\%$ | รันครบ $24 - 48\text{ hrs}$ และค่า Brown Ratio $> 90\%$ | ยิงความร้อน PTC สูง, ปิดช่องระบายอากาศ |
| **STATE_2** | Slow Drying (ไล่ความชื้น) | $35^\circ\text{C} - 38^\circ\text{C}$, $\text{RH} 60 - 70\%$ | มวลรวมลดลงถึงเกณฑ์เป้าหมาย $27\%$ ของน้ำหนักสด (บันทึกผ่าน External Scale + QR Scan) | ยิงความร้อน PTC ปานกลาง, เปิดช่องระบายอากาศ |
| **STATE_3** | Conditioning (Off-Chamber Storage & Periodic Inspection) | $20^\circ\text{C} - 25^\circ\text{C}$, $\text{RH} 65 - 75\%$ ในกล่องไม้ซีดาร์/ไม้สัก (Cedar/Teak Box) ห่อกระดาษไข (Parchment Paper) | ระยะเวลาครบ $\ge 60 - 90\text{ days}$ และผ่านการสแกนตรวจสอบตามรอบ | Off-Chamber / Manual Storage (อุปกรณ์ภายในตู้ทั้งหมดคืนสถานะ Standby) |
| **STATE_E** | Anomaly / Salvage (ฉุกเฉิน) | ระบายอากาศทิ้งทันที | AI Vision ตรวจพบสปอร์รา หรือ อุณหภูมิ $> 58^\circ\text{C}$ | ตัดไฟฮีตเตอร์ทันที, เปิดพัดลมระบายสูงสุด, แจ้งเตือน |

---

## 4. โครงสร้างฐานข้อมูลจัดเก็บข้อมูล (SQLite Schema)

> **หมายเหตุสถาปัตยกรรม:** ฐานข้อมูลจัดเก็บข้อมูลแบบ Local-First (SQLite / Local Storage) สามารถประดิษฐานอยู่บน Smartphone Client หรือ Central Hub พร้อมระบบ Background Sync ขึ้น Cloud เมื่อมีการเชื่อมต่ออินเทอร์เน็ต

- **Table: `batch_metadata` (ข้อมูลประจำแบทช์)**
  - `batch_id` (PK, TEXT): รหัสประจำแบทช์
  - `species` (TEXT): สายพันธุ์ (Planifolia / Tahitensis)
  - `initial_mass_g` (REAL): น้ำหนักสดเริ่มต้น (กรัม)
  - `target_exit_mass_g` (REAL): น้ำหนักเป้าหมายขาออก (1350.0 กรัม = 27%)
  - `start_timestamp` (DATETIME): เวลาที่เริ่มกระบวนการ
  - `current_state` (TEXT): สถานะปัจจุบันของตู้

- **Table: `sensor_telemetry` (บันทึกค่าเซนเซอร์แบบ Time-Series)**
  - `id` (PK, INTEGER AUTOINCREMENT): ไอดีแถวข้อมูล
  - `batch_id` (FK, TEXT): รหัสแบทช์อ้างอิง
  - `timestamp` (DATETIME DEFAULT CURRENT_TIMESTAMP): เวลาที่บันทึก
  - `temperature_c` (REAL): อุณหภูมิปัจจุบัน (°C)
  - `humidity_rh` (REAL): ความชื้นสัมพัทธ์ปัจจุบัน (%RH)
  - `current_mass_g` (REAL): น้ำหนักรวมปัจจุบัน (กรัม - บันทึกจากเครื่องชั่งภายนอก/การคาดการณ์)
  - `heater_state` (INTEGER: 0/1): สถานะฮีตเตอร์ (เปิด/ปิด)
  - `fan_state` (INTEGER: 0/1): สถานะพัดลม (เปิด/ปิด)

- **Table: `vision_inspections` (ผลการตรวจจับด้วย AI Vision รายวัน)**
  - `inspection_id` (PK, INTEGER AUTOINCREMENT): ไอดีผลตรวจ
  - `batch_id` (FK, TEXT): รหัสแบทช์อ้างอิง
  - `timestamp` (DATETIME): เวลาที่บันทึกภาพ
  - `tray_index` (INTEGER): ลำดับชั้นของถาดที่สแกน (1, 2, 3...)
  - `brown_ratio` (REAL): สัดส่วนพื้นที่สีน้ำตาล (% การเปลี่ยนสี)
  - `mold_detected` (BOOLEAN): ตรวจพบเชื้อราหรือไม่ (True/False)
  - `image_path` (TEXT): ตำแหน่งไฟล์ภาพถ่ายที่บันทึกไว้

---

## 5. โมเดลการควบคุม VPD แบบแยกส่วนและลูปซ้อนทับ (Decoupled VPD & Cascaded Mass Control)

### 5.1 สูตรการคำนวณ Vapor Pressure Deficit (Tetens Formula)
ความดันไอน้ำส่วนขาด (VPD) คำนวณแบบ Real-time จากอุณหภูมิอากาศ ($T_{\text{air}}$) และความชื้นสัมพัทธ์ ($\text{RH}_{\text{air}}$) โดยใช้สมการ Tetens Equation:
$$\text{VPD}(T_{\text{air}}, \text{RH}_{\text{air}}) = 0.61078 \times \exp\left(\frac{17.27 \times T_{\text{air}}}{T_{\text{air}} + 237.3}\right) \times \left(1 - \frac{\text{RH}_{\text{air}}}{100}\right) \quad [\text{kPa}]$$

### 5.2 สถาปัตยกรรมลูปควบคุมซ้อนทับ (Cascaded Dual-Loop Control Scheme)
- **Outer Loop (Supervisory Control):** ควบคุมและติดตามอัตราส่วนการสูญเสียมวลรวม (Mass Ratio Target = 27.0% บันทึกผ่านเครื่องชั่งดิจิทัลภายนอก + QR Logging) เมื่อถึงเป้าหมายตู้จะสิ้นสุด Active Chamber Lifecycle
- **Inner Loop (Process Control):** ควบคุมและรักษาสมดุลแรงดันไอน้ำส่วนขาด (VPD Target $\approx 1.0\text{ kPa}$ ในช่วง Slow Drying) ผ่านการปรับตำแหน่งช่องระบายอากาศ (Exhaust Vent) ร่วมกับการชดเชยอุณหภูมิจาก PTC Heater

### 5.3 ลำดับความสำคัญในการสั่งการอุปกรณ์ (Decoupled Actuator Priority Matrix)
1. **Circulating Fan (พัดลมหมุนเวียน):** ทำงานในโหมด Constant Airflow หมุนเวียนอากาศต่อเนื่องตลอดกระบวนบ่ม เพื่อรักษาการกระจายความร้อนและป้องกันจุดอับอากาศ (Dead zones)
2. **PTC Heater (ฮีตเตอร์):** ทำหน้าที่ Dedicated Temperature Control ควบคุมอุณหภูมิให้อยู่ในกรอบเป้าหมาย ($45^\circ\text{C}-50^\circ\text{C}$ สำหรับ Sweating และ $35^\circ\text{C}-38^\circ\text{C}$ สำหรับ Slow Drying)
3. **Exhaust Vent (ช่องระบายอากาศ):** ทำหน้าที่ Closed-loop VPD Modulation ปรับมุมเปิด-ปิดแบบ Stepwise มีช่วง Hysteresis Deadband $[0.9, 1.1]\text{ kPa}$ ประเมินผลรอบละ 30–60 วินาที

### 5.4 ระบบความปลอดภัยและขีดจำกัดวิกฤต (Fallback Safety Thresholds)
- **Hard Over-Temperature Cutoff:** ตัดไฟ PTC Heater ทันทีผ่าน Hardware/Software Relay เมื่ออุณหภูมิสูงกว่า $58.0^\circ\text{C}$
- **Sensor Failsafe:** หากเซนเซอร์ SHT31 ขัดข้อง/ไม่สามารถอ่านค่าได้ ระบบจะตัดการทำงานของฮีตเตอร์ สั่งเปิดพัดลมระบายสูงสุด และแจ้งเตือนสถานะฉุกเฉิน

---

## 6. สถาปัตยกรรมแบบแยกส่วนและการเพิ่มประสิทธิภาพด้วยผลสัมผัส (Decoupled Architecture & Closed-Loop Sensory Optimization)

### 6.1 ภาพรวมสถาปัตยกรรม 3 ชั้น (Three-Layer Decoupled Architecture)
1. **Chamber Hardware Pod (ESP32):** ทำหน้าที่เป็น Reliable Actuator ควบคุมสภาวะแวดล้อม Closed-loop $T, \text{RH}, \text{VPD}$ ตาม Recipe ($T, \text{VPD}, \text{Time}$) โดยใช้อินพุตจาก SHT31 และปราศจากกล้อง/โหลดเซลล์ภายในตู้เพื่อความทนทานสูงสุด
2. **Batch Traceability Layer (Mobile/Web):** ติดตามฝักระดับถาดผ่านระบบ **QR Code Tracking** บันทึกการเปลี่ยนแปลงน้ำหนัก ($M_t \rightarrow 27\%$) จากเครื่องชั่งดิจิทัลภายนอก และภาพถ่าย (Color & Texture Analysis)
3. **Sensory & Optimization Engine:** เชื่อมโยงผลวิเคราะห์คุณภาพขั้นสุดท้าย (% Vanillin HPLC และ Sensory Cupping Radar Score) ป้อนกลับ (Feedback Loop) เข้าสมการเพื่อปรับปรุงและ Optimize ค่า Recipe ($T, \text{VPD}, \text{Time}$) สำหรับแบทช์ถัดไป

### 6.2 สเปกอุปกรณ์และผลผลิตเป้าหมาย (Hardware & Prototype Parameters)
- **ความจุเป้าหมาย:** ฝักสด 5.0 kg (~250–350 ฝัก) เหมาะสมกับสวนวานิลลาขนาด 1 งาน (ผลผลิตรวม ~200–250 kg/ปี ทยอยออก 12 สัปดาห์)
- **กายภาพถาดบ่ม:** ถาดตะแกรง Mesh Tray ขนาด $30 \times 40\text{ cm}$ จำนวน 4 ชั้น (พื้นที่รวม $\ge 0.40\text{ m}^2$)
- **Dual-Stage Profile (ตู้บ่มเดี่ยว):**
  - **Stage 1 (Sweating):** ระยะเวลา 24–48 ชม., อุณหภูมิ $T_{\text{air}} = 45^\circ\text{C} - 50^\circ\text{C}$, ปิด Vent สนิท ($\text{RH} > 85\%$), $\text{VPD} \approx 0.3 - 0.5\text{ kPa}$
  - **Stage 2 (Slow Drying):** ระยะเวลา 10–14 วัน, อุณหภูมิ $T_{\text{air}} = 35^\circ\text{C} - 38^\circ\text{C}$, ปรับ Vent ควบคุมสมดุล $\text{VPD} \approx 1.0\text{ kPa}$
  - **Exit Condition:** อัตราส่วนมวลคงเหลือแตะ $27.0\%$ ($M_{\text{exit}} = 1.35\text{ kg}$ บันทึกภายนอกผ่าน QR Code Scan)

### 6.3 โครงสร้างการประเมินผลสัมผัส (Sensory Evaluation Metrics)
- **% Vanillin Content (HPLC):** Target $\ge 2.0\%$
- **Sensory Radar Attributes (Scale 0.0 - 10.0):**
  - `sweetness` (ความหวานกลมกล่อม)
  - `creamy` (ความหอมมันแบบครีม)
  - `floral` (ความหอมดอกไม้)
  - `woody` (ความหอมไม้แบบวานิลลาบ่ม)
  - `defect_off_flavor` (กลิ่นแปลกปลอม/กลิ่นอับ ต้อง $\le 1.0$)

---

## 7. เกณฑ์การยอมรับเพื่อส่งมอบงาน (Acceptance Criteria)
1. **Zero-Deadlock Telemetry:** ฐานข้อมูล SQLite ต้องรองรับการเขียนข้อมูลเซนเซอร์ทุก 5 วินาทีได้อย่างต่อเนื่องโดยไม่เกิด Database Lock
2. **Thermal Safety Guard:** ระบบ Hardware Watchdog ต้องตัดการทำงานของฮีตเตอร์ทันทีเมื่ออุณหภูมิเกิน $58^\circ\text{C}$
3. **Loss-of-Mass Release & Chamber Throughput:** เมื่อค่าน้ำหนักรวมลดลงถึงเกณฑ์เป้าหมาย $27.0\% \pm 1.0\%$ จากการชั่งน้ำหนักภายนอกและสแกน QR Code ระบบตู้บ่มจะสิ้นสุด active lifecycle และเปลี่ยนสถานะตู้เป็น `READY_FOR_NEXT_BATCH` เพื่อปลดล็อกตู้สำหรับแบทช์ถัดไป และย้ายฝักไปบ่มต่อภายนอก (Off-Chamber Conditioning)