# พิมพ์เขียวระบบ: ตู้บ่มวานิลลาอัตโนมัติ (AUTOMATED VANILLA CURING HUB - 5KG PROTOTYPE)

## 1. ขอบเขตและข้อจำกัดของระบบ (System Boundary & Scope)
- **ขนาดความจุเป้าหมาย (Target Capacity):** ฝักวานิลลาสด 5.0 kg (~250–350 ฝัก)
- **สถาปัตยกรรมทางกายภาพ (Physical Architecture):** 
  - ภายในตู้: ถาดตะแกรงซ้อนกัน 3–4 ชั้น (Multi-tier Mesh Trays) พร้อมระบบหมุนเวียนลมร้อนแบบบังคับทิศทาง (Forced Convection)
  - กระบวนการตรวจสอบ (Smartphone-Centric Workflow): ใช้กล้องสมาร์ทโฟนถ่ายภาพมาโครประจำวัน (Daily Macro Snapshots) ควบคู่กับการประมวลผลด้วย On-device Edge AI Inference โดยไม่ต้องใช้แท่นถ่ายภาพแยก
- **ขอบเขตกระบวนการอัตโนมัติ (Automated Chamber Scope):** ระบบตู้บ่มอัตโนมัติรองรับและควบคุมสภาพแวดล้อมตั้งแต่มวลสดเข้าตู้จนจบช่วง active chamber lifecycle ได้แก่ **STATE_0 (Pre-Kill & Sizing)**, **STATE_1 (Sweating)** ถึง **STATE_2 (Slow Drying)**
- **การย้ายกระบวนการบ่มนอกตู้ (Off-Chamber Conditioning):** ขั้นตอน **STATE_3 (Conditioning)** ถูก Offload ไปยังกล่องไม้ภายนอก (Manual/Off-chamber Storage) เพื่อคืนพื้นที่ภายในตู้ (Free up chamber throughput) ทำให้ตู้พร้อมเริ่มรองรับแบทช์ใหม่ได้ทันที
- **สิ่งที่ไม่ทำเด็ดขาด (Explicit Out of Scope):**
  - ไม่ติดตั้งกล้องภายในตู้ (ตัดปัญหากล้องขึ้นฝ้า ไอน้ำเกาะ และความร้อนสะสม)
  - ไม่ติดโหลดเซลล์แยกทีละฝัก (ใช้โหลดเซลล์รวมคำนวณมวลรวมของแบทช์)

---

## 2. ทิศทางการไหลของข้อมูลและสถาปัตยกรรม (Topology & Data Flow)

```
+-------------------------------------------------------+
|              ESP32 Chamber Controller                 |
|  [Sensors: SHT31, Load Cell]                          |
|  [Actuators: PTC Heater, Fan, Vent Relays]            |
|  [Firmware: FSM Loop & Safety Watchdog]               |
+-------------------------------------------------------+
                           ▲
                           │  Dual-Mode Connectivity
                           │  (BLE GATT / Wi-Fi REST & WebSockets)
                           ▼
+-------------------------------------------------------+
|          Smartphone Client & Edge AI Brain            |
|  [User Interface: Mobile Dashboard & Controls]        |
|  [Vision Engine: OpenCV (Color/Brown Ratio)]          |
|  [Edge AI Model: Gemini Nano / On-device Multimodal]  |
|  [Local Database: SQLite / IndexedDB + Cloud Sync]    |
+-------------------------------------------------------+
```

- **Chamber Controller & Actuators:** ESP32 Chamber Controller ทำหน้าที่รัน FSM Loop อ่านค่าเซนเซอร์ (SHT31, Load Cell) และสั่งการ Relays ควบคุมอุปกรณ์ทำความร้อน (PTC Heater), พัดลม (Fan) และช่องระบายอากาศ (Vent) พร้อมระบบ Hardware Watchdog
- **ระบบการเชื่อมต่อแบบสองโหมด (Dual-Mode Connectivity):**
  - **BLE (Bluetooth Low Energy GATT Service):** สำหรับการเชื่อมต่อ direct offline สั่งการและอ่านค่าเซนเซอร์ในระยะใกล้โดยไม่ต้องพึ่งพาเครือข่าย
  - **Wi-Fi (HTTP/WebSockets REST API):** สำหรับการสื่อสารแบบเรียลไทม์ภายในเครือข่ายท้องถิ่น (LAN)
- **แอปพลิเคชันฝั่งผู้ใช้และสมองกลประมวลผล (Client & Vision Brain):** Smartphone Application หรือ Web App ทำหน้าที่เป็น Dashboard แสดงผล บันทึกฐานข้อมูล และทำหน้าที่เป็น On-device Edge AI Engine:
  - **OpenCV Engine:** คำนวณสัดส่วนสีผิวฝัก (Color / Brown Ratio) เพื่อประเมินความสุกและระดับการเปลี่ยนสี
  - **Gemini Nano / On-device Multimodal LLM:** วิเคราะห์รอยตำหนิ และตรวจจับสปอร์เชื้อรา (Mold & Defect Detection) บนตัวฝักวานิลลาโดยตรงบนสมาร์ทโฟน

---

## 3. ตารางตรรกะการเปลี่ยนสถานะ (Deterministic State Machine)

| State ID | ชื่อเฟส (Phase Name) | สภาพแวดล้อมเป้าหมาย | เงื่อนไขการเปลี่ยนสถานะ (Exit Condition) | การสั่งการอุปกรณ์ (Actuator Behavior) |
|---|---|---|---|---|
| **STATE_0** | Pre-Kill & Sizing | อุณหภูมิห้องปกติ | ยืนยันขนาดฝักผ่านภาพถ่าย (กำหนดค่า $t_{kill}$) | Standby (ปิดทุกอย่าง) |
| **STATE_1** | Sweating (กระตุ้นเอนไซม์) | $45^\circ\text{C} - 50^\circ\text{C}$, $\text{RH} > 85\%$ | รันครบ $24 - 48\text{ hrs}$ และค่า Brown Ratio $> 90\%$ | ยิงความร้อน PTC สูง, ปิดช่องระบายอากาศ |
| **STATE_2** | Slow Drying (ไล่ความชื้น) | $35^\circ\text{C} - 38^\circ\text{C}$, $\text{RH} 60 - 70\%$ | มวลรวมลดลงถึงเกณฑ์เป้าหมาย $27\%$ ของน้ำหนักสด (สิ้นสุด Active Chamber Lifecycle) | ยิงความร้อน PTC ปานกลาง, เปิดช่องระบายอากาศ |
| **STATE_3** | Conditioning (Off-Chamber Storage & Periodic Inspection) | $20^\circ\text{C} - 25^\circ\text{C}$, $\text{RH} 65 - 75\%$ ในกล่องไม้ซีดาร์/ไม้สัก (Cedar/Teak Box) ห่อกระดาษไข (Parchment Paper) | ระยะเวลาครบ $\ge 60 - 90\text{ days}$ และผ่านการสแกนตรวจสอบตามรอบ | Off-Chamber / Manual Storage (อุปกรณ์ภายในตู้ทั้งหมดคืนสถานะ Standby) |
| **STATE_E** | Anomaly / Salvage (ฉุกเฉิน) | ระบายอากาศทิ้งทันที | AI Vision ตรวจพบสปอร์รา หรือ อุณหภูมิ $> 58^\circ\text{C}$ | ตัดไฟฮีตเตอร์ทันที, เปิดพัดลมระบายสูงสุด, แจ้งเตือน |

---

## 4. โครงสร้างฐานข้อมูลจัดเก็บข้อมูล (SQLite Schema)

> **หมายเหตุสถาปัตยกรรม:** ฐานข้อมูลจัดเก็บข้อมูลแบบ Local-First (SQLite / Local Storage) สามารถประดิษฐานอยู่บน Smartphone Client หรือ Central Hub พร้อมระบบ Background Sync ขึ้น Cloud เมื่อมีการเชื่อมต่ออินเทอร์เน็ต

- **Table: `batch_metadata` (ข้อมูลประจำแบทช์)**
  - `batch_id` (PK, TEXT): รหัสประจำแบทช์
  - `species` (TEXT): สายพันธุ์ (Planifolia / Tahitensis)
  - `initial_mass_g` (REAL): น้ำหนักสดเริ่มต้น (กรัม)
  - `start_timestamp` (DATETIME): เวลาที่เริ่มกระบวนการ
  - `current_state` (TEXT): สถานะปัจจุบันของตู้

- **Table: `sensor_telemetry` (บันทึกค่าเซนเซอร์แบบ Time-Series)**
  - `id` (PK, INTEGER AUTOINCREMENT): ไอดีแถวข้อมูล
  - `batch_id` (FK, TEXT): รหัสแบทช์อ้างอิง
  - `timestamp` (DATETIME DEFAULT CURRENT_TIMESTAMP): เวลาที่บันทึก
  - `temperature_c` (REAL): อุณหภูมิปัจจุบัน (°C)
  - `humidity_rh` (REAL): ความชื้นสัมพัทธ์ปัจจุบัน (%RH)
  - `current_mass_g` (REAL): น้ำหนักรวมปัจจุบัน (กรัม)
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

## 5. เกณฑ์การยอมรับเพื่อส่งมอบงาน (Acceptance Criteria)
1. **Zero-Deadlock Telemetry:** ฐานข้อมูล SQLite ต้องรองรับการเขียนข้อมูลเซนเซอร์ทุก 5 วินาทีได้อย่างต่อเนื่องโดยไม่เกิด Database Lock
2. **Thermal Safety Guard:** ระบบ Hardware Watchdog ต้องตัดการทำงานของฮีตเตอร์ทันทีเมื่ออุณหภูมิเกิน $58^\circ\text{C}$
3. **Loss-of-Mass Release & Chamber Throughput:** เมื่อค่าน้ำหนักรวมลดลงถึงเกณฑ์เป้าหมาย $27.0\% \pm 1.0\%$ จากโหลดเซลล์ ระบบตู้บ่มจะสิ้นสุด active lifecycle และเปลี่ยนสถานะตู้เป็น `READY_FOR_NEXT_BATCH` เพื่อปลดล็อกตู้สำหรับแบทช์ถัดไป และย้ายฝักไปบ่มต่อภายนอก (Off-Chamber Conditioning)