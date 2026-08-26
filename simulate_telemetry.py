import sqlite3
import random
import time

DB_NAME = "curing_hub.db"
BATCH_ID = "BATCH-202608-01"

def get_connection():
    conn = sqlite3.connect(DB_NAME, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def ensure_batch_exists():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT batch_id FROM batch_metadata WHERE batch_id = ?", (BATCH_ID,))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO batch_metadata (batch_id, species, initial_mass_g, current_state)
                VALUES (?, ?, ?, ?)
            """, (BATCH_ID, "Planifolia", 5000.0, "STATE_1_SWEATING"))
            print(f"Batch '{BATCH_ID}' initialized in batch_metadata.")
        else:
            print(f"Batch '{BATCH_ID}' already exists in batch_metadata.")

def run_simulation(num_readings=10):
    ensure_batch_exists()
    
    current_mass = 5000.0
    print(f"\nSimulating {num_readings} telemetry readings for batch '{BATCH_ID}'...")

    for i in range(num_readings):
        # Temperature ~45-48°C, RH ~85-90%, Mass gradually decreasing from 5000g
        temp = round(random.uniform(45.0, 48.0), 2)
        humidity = round(random.uniform(85.0, 90.0), 2)
        current_mass -= round(random.uniform(0.5, 2.0), 2)
        heater_state = 1
        fan_state = 1

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sensor_telemetry (batch_id, temperature_c, humidity_rh, current_mass_g, heater_state, fan_state)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (BATCH_ID, temp, humidity, current_mass, heater_state, fan_state))
        
        time.sleep(0.05)

    print("\nDatabase Verification - Telemetry Records:")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, batch_id, timestamp, temperature_c, humidity_rh, current_mass_g, heater_state, fan_state
            FROM sensor_telemetry
            WHERE batch_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (BATCH_ID, num_readings))
        rows = cursor.fetchall()
        
        header = f"{'ID':<6} | {'Batch ID':<17} | {'Timestamp':<20} | {'Temp (°C)':<9} | {'RH (%)':<8} | {'Mass (g)':<9} | {'Heater':<6} | {'Fan':<5}"
        divider = "-" * len(header)
        print(divider)
        print(header)
        print(divider)
        for row in reversed(rows):
            print(f"{row[0]:<6} | {row[1]:<17} | {str(row[2]):<20} | {row[3]:<9.2f} | {row[4]:<8.2f} | {row[5]:<9.2f} | {row[6]:<6} | {row[7]:<5}")
        print(divider)

if __name__ == "__main__":
    run_simulation(10)
