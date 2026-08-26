# รายการอุปกรณ์ฮาร์ดแวร์ (Bill of Materials - BOM)
## ตู้บ่มวานิลลาอัตโนมัติ (Automated Vanilla Curing Hub - 5kg Prototype)

เอกสารฉบับนี้ใช้เป็น **Single Source of Truth** สำหรับการจัดซื้ออุปกรณ์ วางแผนวงจรอิเล็กทรอนิกส์ และประกอบตู้บ่มวานิลลาอัตโนมัติความจุ 5.0 kg

---

## 1. หน่วยประมวลผลและการแสดงผล (Compute & Control)
| อุปกรณ์ (Component) | สเปกทางเทคนิค (Technical Specification) | จำนวน (Qty) | หน่วย (Unit) | วัตถุประสงค์และการใช้งาน (Purpose) |
|---|---|---|---|---|
| **ESP32 Development Board** | 38 Pins, Dual-Core 240MHz, Wi-Fi & BLE Dual-Mode | 1 | บอร์ด | ประมวลผล FSM Loop, อ่านค่าเซนเซอร์, ควบคุม Actuator และสื่อสารข้อมูล |
| **OLED Display 0.96"** | Resolution 128x64 pixels, I2C Interface (Address 0x3C) | 1 | จอ | แสดงผลข้อมูลอุณหภูมิ, RH, VPD และสถานะตู้แบบ Real-time |

---

## 2. เซนเซอร์ตรวจวัดภายในตู้ (In-Chamber Sensing Layer)
| อุปกรณ์ (Component) | สเปกทางเทคนิค (Technical Specification) | จำนวน (Qty) | หน่วย (Unit) | วัตถุประสงค์และการใช้งาน (Purpose) |
|---|---|---|---|---|
| **SHT31 Sensor Module** | High Accuracy Temp (±0.2°C) & RH (±2%), I2C Interface | 1 | ตัว | ตรวจวัดอุณหภูมิและความชื้นสัมพัทธ์ในตู้บ่มเพื่อคำนวณค่า VPD สัมพัทธ์แบบ Closed-Loop |

---

## 3. อุปกรณ์ชั่งน้ำหนักภายนอก (External Weight Tracking & QR Logging)
| อุปกรณ์ (Component) | สเปกทางเทคนิค (Technical Specification) | จำนวน (Qty) | หน่วย (Unit) | วัตถุประสงค์และการใช้งาน (Purpose) |
|---|---|---|---|---|
| **External Digital Bench/Kitchen Scale** | Precision 0.1g / 1g Resolution, Max Capacity 10.0 kg | 1 | เครื่อง | เครื่องชั่งน้ำหนักดิจิทัลภายนอก ชั่งน้ำหนักถาดฝักวานิลลาสดก่อนเข้าตู้และสแกน QR Code บันทึกลงแอปพลิเคชัน (ตัดปัญหา Sensor Drift จากอุณหภูมิและความชื้นสะสมภายในตู้) |

---

## 4. ระบบทำความร้อนและการขับเคลื่อน (Thermal & Actuation Layer)
| อุปกรณ์ (Component) | สเปกทางเทคนิค (Technical Specification) | จำนวน (Qty) | หน่วย (Unit) | วัตถุประสงค์และการใช้งาน (Purpose) |
|---|---|---|---|---|
| **PTC Heating Element** | 200W 12V/220V Constant Temperature PTC Air Heater | 1 | ชิ้น | ให้ความร้อนภายในตู้บ่มสำหรับเฟส Sweating (45-50°C) และ Slow Drying (35-38°C) |
| **Solid State Relay (SSR)** | SSR-25DA (Control 3-32VDC, Output 24-380VAC / 25A) | 1 | ตัว | ตัด-ต่อการทำงานของ PTC Heater แบบสวิตช์อิเล็กทรอนิกส์ไร้หน้าสัมผัส |
| **Brushless DC Fan 12V** | 92mm x 92mm High-Airflow DC Fan (Constant Airflow Mode) | 2 | ตัว | หมุนเวียนอากาศภายในตู้แบบ Forced Convection เพื่อป้องกันจุดอับความร้อน |
| **Servo Motor MG996R** | High Torque Metal Gear Servo (10kg-cm @ 6V), 0-180° | 1 | ตัว | ปรับมุมเปิด-ปิดช่องระบายอากาศ (Exhaust Vent) เพื่อควบคุมค่า VPD สัมพัทธ์ |

---

## 5. ระบบจ่ายไฟและป้องกันวงจร (Power & Electrical Protection)
| อุปกรณ์ (Component) | สเปกทางเทคนิค (Technical Specification) | จำนวน (Qty) | หน่วย (Unit) | วัตถุประสงค์และการใช้งาน (Purpose) |
|---|---|---|---|---|
| **Switching Power Supply 12V** | Output 12V DC 5A (60W), AC 110/220V Input | 1 | ตัว | จ่ายพลังงานไฟฟ้ากระแสตรง 12V ให้บอร์ด, เซอร์โว, พัดลม และอุปกรณ์ควบคุม |
| **Fuse Holder & 5A Fuse** | Panel Mount Fuse Holder with 5A Fast-Acting Glass Fuse | 1 | ชุด | ป้องกันกระแสไฟฟ้าเกินและป้องกันลัดวงจรสำหรับระบบทำความร้อนและภาคจ่ายไฟ |
| **Screw Terminal Block** | 5A Barrier Terminal Block (4-6 Positions) | 2 | แผง | สำหรับจุดต่อสายไฟจุดรวมแรงดันและสายสัญญาณเพื่อความปลอดภัยและเรียบร้อย |

---

## 6. โครงสร้างตู้และกลไก (Chamber & Mechanical Structure)
| อุปกรณ์ (Component) | สเปกทางเทคนิค (Technical Specification) | จำนวน (Qty) | หน่วย (Unit) | วัตถุประสงค์และการใช้งาน (Purpose) |
|---|---|---|---|---|
| **Insulated Chamber Enclosure** | ความจุ ~78 Liters, ผนังบุฉนวนกันความร้อน (PU / EPS Foam) | 1 | ตู้ | หุ้มห่อกักเก็บความร้อนและความชื้น ป้องกันความร้อนสูญเสียสู่ภายนอก |
| **Stainless Steel Mesh Trays** | ขนาด $30 \times 40\text{ cm}$, ถาดตะแกรง สแตนเลส 304 Food-Grade | 4 | ถาด | วางฝักวานิลลาสด 4 ชั้น (พื้นที่รวม $\ge 0.40\text{ m}^2$) ให้ลมร้อนผ่านสะดวก |
