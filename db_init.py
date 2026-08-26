import sqlite3

DB_NAME = "curing_hub.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Enable WAL (Write-Ahead Logging) mode and foreign keys
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")

    # Table: batch_metadata
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS batch_metadata (
        batch_id TEXT PRIMARY KEY,
        species TEXT,
        initial_mass_g REAL,
        target_exit_mass_g REAL DEFAULT 1350.0,
        start_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        current_state TEXT
    );
    """)

    # Ensure target_exit_mass_g column exists if table was previously created
    try:
        cursor.execute("ALTER TABLE batch_metadata ADD COLUMN target_exit_mass_g REAL DEFAULT 1350.0;")
    except sqlite3.OperationalError:
        pass

    # Table: sensor_telemetry
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sensor_telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        temperature_c REAL,
        humidity_rh REAL,
        current_mass_g REAL,
        heater_state INTEGER CHECK (heater_state IN (0, 1)),
        fan_state INTEGER CHECK (fan_state IN (0, 1)),
        FOREIGN KEY (batch_id) REFERENCES batch_metadata (batch_id) ON DELETE CASCADE
    );
    """)

    # Table: vision_inspections
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vision_inspections (
        inspection_id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        tray_index INTEGER,
        brown_ratio REAL,
        mold_detected BOOLEAN,
        image_path TEXT,
        FOREIGN KEY (batch_id) REFERENCES batch_metadata (batch_id) ON DELETE CASCADE
    );
    """)

    # Table: sensory_evaluations (Closed-Loop Optimization Feedback)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sensory_evaluations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id TEXT,
        vanillin_hplc_pct REAL,
        sweetness REAL,
        creamy REAL,
        floral REAL,
        woody REAL,
        defect_off_flavor REAL,
        eval_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (batch_id) REFERENCES batch_metadata (batch_id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()
    print(f"Database '{DB_NAME}' initialized successfully with WAL mode and sensory_evaluations schema.")

if __name__ == "__main__":
    init_db()
