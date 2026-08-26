"""
Vanilla Curing Hub - Finite State Machine (FSM) Controller
Orchestrates batch lifecycle transitions based on sensor telemetry,
vision inspection reports, and safety watchdog rules.
"""

from dataclasses import dataclass
from datetime import datetime
import logging
import sqlite3
from typing import Dict, Optional, Tuple, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FSMController")

DB_NAME = "curing_hub.db"

# State Constants
STATE_0 = "STATE_0"  # Pre-Kill & Sizing
STATE_1 = "STATE_1"  # Sweating (Enzyme Activation)
STATE_2 = "STATE_2"  # Slow Drying (Moisture Reduction)
READY_FOR_NEXT_BATCH = "READY_FOR_NEXT_BATCH"  # Completed active lifecycle & Offloaded
STATE_E = "STATE_E"  # Emergency Salvage

class VanillaFSMController:
    """
    Deterministic FSM Engine evaluating state transitions and controlling actuators.
    """

    def __init__(self, db_name: str = DB_NAME) -> None:
        self.db_name = db_name

    def get_db_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_name, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def fetch_batch_context(self, batch_id: str) -> Tuple[Optional[dict], Optional[dict], Optional[dict]]:
        """
        Fetches latest batch metadata, latest telemetry, and latest vision inspection.
        """
        with self.get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 1. Fetch metadata
            cursor.execute("SELECT * FROM batch_metadata WHERE batch_id = ?", (batch_id,))
            meta_row = cursor.fetchone()
            meta = dict(meta_row) if meta_row else None

            # 2. Fetch latest telemetry
            cursor.execute(
                "SELECT * FROM sensor_telemetry WHERE batch_id = ? ORDER BY id DESC LIMIT 1",
                (batch_id,)
            )
            telem_row = cursor.fetchone()
            telem = dict(telem_row) if telem_row else None

            # 3. Fetch latest vision inspection
            cursor.execute(
                "SELECT * FROM vision_inspections WHERE batch_id = ? ORDER BY inspection_id DESC LIMIT 1",
                (batch_id,)
            )
            vision_row = cursor.fetchone()
            vision = dict(vision_row) if vision_row else None

        return meta, telem, vision

    def evaluate_batch_state(
        self,
        batch_id: str,
        override_elapsed_hours: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Evaluates state transition conditions deterministically and updates batch metadata.
        Returns a dictionary containing transition details and actuator commands.
        """
        meta, telem, vision = self.fetch_batch_context(batch_id)

        if not meta:
            raise ValueError(f"Batch metadata not found for batch_id: '{batch_id}'")

        current_state = meta.get("current_state", STATE_0)
        initial_mass_g = meta.get("initial_mass_g", 5000.0)

        # -------------------------------------------------------------
        # 1. EMERGENCY SAFETY WATCHDOG (Checked regardless of state)
        # -------------------------------------------------------------
        latest_temp = telem.get("temperature_c", 0.0) if telem else 0.0
        mold_detected = bool(vision.get("mold_detected", False)) if vision else False

        if latest_temp > 58.0 or mold_detected:
            reasons = []
            if latest_temp > 58.0:
                reasons.append(f"Over-temperature detected ({latest_temp:.1f}°C > 58.0°C)")
            if mold_detected:
                reasons.append("Mold / fungal spore detected by Edge AI Vision")

            new_state = STATE_E
            reason_str = " | ".join(reasons)
            logger.critical(f"[EMERGENCY ABORT] Batch {batch_id}: {reason_str}")
            return self._update_and_build_payload(batch_id, current_state, new_state, reason_str)

        # -------------------------------------------------------------
        # 2. DETERMINISTIC STATE MACHINE LOGIC
        # -------------------------------------------------------------
        new_state = current_state
        reason_str = "No transition criteria met."

        if current_state == STATE_0:
            # STATE_0 -> STATE_1: Verified initialization
            if initial_mass_g > 0:
                new_state = STATE_1
                reason_str = "Batch initialization verified. Transitioning to Sweating phase."

        elif current_state == STATE_1:
            # STATE_1 -> STATE_2: Brown ratio >= 90% AND Sweating duration met (>= 24 hrs)
            brown_ratio = vision.get("brown_ratio", 0.0) if vision else 0.0

            if override_elapsed_hours is not None:
                elapsed_hours = override_elapsed_hours
            else:
                start_time_str = meta.get("start_timestamp")
                try:
                    start_dt = datetime.fromisoformat(start_time_str)
                    elapsed_hours = (datetime.now() - start_dt).total_seconds() / 3600.0
                except Exception:
                    elapsed_hours = 0.0

            if brown_ratio >= 90.0 and elapsed_hours >= 24.0:
                new_state = STATE_2
                reason_str = f"Sweating complete (Brown ratio {brown_ratio:.1f}% >= 90%, Elapsed {elapsed_hours:.1f}h >= 24h). Transitioning to Slow Drying."

        elif current_state == STATE_2:
            # STATE_2 -> READY_FOR_NEXT_BATCH: Mass reduced to <= 27% target
            current_mass_g = telem.get("current_mass_g", initial_mass_g) if telem else initial_mass_g
            mass_ratio = (current_mass_g / initial_mass_g) if initial_mass_g > 0 else 1.0

            if mass_ratio <= 0.27:
                new_state = READY_FOR_NEXT_BATCH
                reason_str = f"Mass target reached ({mass_ratio * 100.0:.1f}% <= 27.0%). Chamber active lifecycle complete. Offloading to wooden box."

        # -------------------------------------------------------------
        # 3. APPLY STATE UPDATE IF CHANGED
        # -------------------------------------------------------------
        return self._update_and_build_payload(batch_id, current_state, new_state, reason_str)

    def _update_and_build_payload(
        self,
        batch_id: str,
        current_state: str,
        new_state: str,
        reason: str
    ) -> Dict[str, Any]:
        transitioned = (current_state != new_state)

        if transitioned:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE batch_metadata SET current_state = ? WHERE batch_id = ?",
                    (new_state, batch_id)
                )
            logger.info(f"FSM Transition for Batch '{batch_id}': {current_state} -> {new_state} ({reason})")

        actuator_cmds = self.generate_actuator_commands(new_state)

        return {
            "batch_id": batch_id,
            "previous_state": current_state,
            "current_state": new_state,
            "transitioned": transitioned,
            "reason": reason,
            "actuator_commands": actuator_cmds,
            "evaluated_at": datetime.now().isoformat()
        }

    def generate_actuator_commands(self, current_state: str) -> Dict[str, Any]:
        """
        Generates target environmental setpoints and relay control signals.
        """
        table = {
            STATE_0: {
                "target_temp_c": None,
                "target_rh_percent": None,
                "heater_relay": 0,
                "fan_relay": 0,
                "vent_relay": 0,
                "description": "Standby - Pre-Kill & Sizing"
            },
            STATE_1: {
                "target_temp_c": 47.5,
                "target_rh_percent": 87.5,
                "heater_relay": 1,
                "fan_relay": 1,
                "vent_relay": 0,
                "description": "Sweating Phase - High PTC Heat, Closed Vents"
            },
            STATE_2: {
                "target_temp_c": 36.5,
                "target_rh_percent": 65.0,
                "heater_relay": 1,
                "fan_relay": 1,
                "vent_relay": 1,
                "description": "Slow Drying Phase - Moderate Heat, Open Vents"
            },
            READY_FOR_NEXT_BATCH: {
                "target_temp_c": None,
                "target_rh_percent": None,
                "heater_relay": 0,
                "fan_relay": 0,
                "vent_relay": 0,
                "description": "Chamber Released - Off-Chamber Conditioning in Wooden Box"
            },
            STATE_E: {
                "target_temp_c": 0.0,
                "target_rh_percent": 0.0,
                "heater_relay": 0,  # EMERGENCY CUTOFF
                "fan_relay": 1,     # MAX BLOWER
                "vent_relay": 1,    # MAX EXHAUST VENT
                "description": "EMERGENCY ABORT - Heater cutoff, max exhaust purging"
            }
        }
        return table.get(current_state, table[STATE_0])

# =====================================================================
# Automated Verification & Unit Test Suite
# =====================================================================

def run_fsm_tests():
    print("=====================================================================")
    print("            AUTOMATED FSM CONTROLLER TEST SUITE                      ")
    print("=====================================================================")

    fsm = VanillaFSMController()
    test_batch = "BATCH-TEST-FSM"

    # Reset test batch in database
    with fsm.get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM batch_metadata WHERE batch_id = ?", (test_batch,))
        cursor.execute("DELETE FROM sensor_telemetry WHERE batch_id = ?", (test_batch,))
        cursor.execute("DELETE FROM vision_inspections WHERE batch_id = ?", (test_batch,))

        cursor.execute("""
            INSERT INTO batch_metadata (batch_id, species, initial_mass_g, current_state)
            VALUES (?, 'Planifolia', 5000.0, 'STATE_0')
        """, (test_batch,))

    # --- Test 1: STATE_0 -> STATE_1 Transition ---
    print("\n--- Test 1: STATE_0 -> STATE_1 (Sweating Initialization) ---")
    res1 = fsm.evaluate_batch_state(test_batch)
    print(f"Transition: {res1['previous_state']} -> {res1['current_state']}")
    print(f"Reason:     {res1['reason']}")
    print(f"Actuator:   {res1['actuator_commands']['description']}")
    assert res1['current_state'] == STATE_1, "Expected transition to STATE_1"
    assert res1['actuator_commands']['heater_relay'] == 1, "Expected PTC Heater ON"

    # --- Test 2: STATE_1 -> STATE_2 Transition (Sweating -> Slow Drying) ---
    print("\n--- Test 2: STATE_1 -> STATE_2 (Brown Ratio >= 90% & Time Met) ---")
    with fsm.get_db_connection() as conn:
        cursor = conn.cursor()
        # Insert telemetry (Normal temp)
        cursor.execute("""
            INSERT INTO sensor_telemetry (batch_id, temperature_c, humidity_rh, current_mass_g, heater_state, fan_state)
            VALUES (?, 47.0, 87.0, 4800.0, 1, 1)
        """, (test_batch,))
        # Insert vision inspection (Brown ratio 92.5%)
        cursor.execute("""
            INSERT INTO vision_inspections (batch_id, tray_index, brown_ratio, mold_detected, image_path)
            VALUES (?, 1, 92.5, 0, 'mock_path.jpg')
        """, (test_batch,))

    res2 = fsm.evaluate_batch_state(test_batch, override_elapsed_hours=25.0)
    print(f"Transition: {res2['previous_state']} -> {res2['current_state']}")
    print(f"Reason:     {res2['reason']}")
    print(f"Actuator:   {res2['actuator_commands']['description']}")
    assert res2['current_state'] == STATE_2, "Expected transition to STATE_2"
    assert res2['actuator_commands']['vent_relay'] == 1, "Expected Vent OPEN in STATE_2"

    # --- Test 3: STATE_2 -> READY_FOR_NEXT_BATCH Transition (Mass Target 27%) ---
    print("\n--- Test 3: STATE_2 -> READY_FOR_NEXT_BATCH (Mass <= 27% Target) ---")
    with fsm.get_db_connection() as conn:
        cursor = conn.cursor()
        # Insert telemetry with mass = 1300g (26% of 5000g initial)
        cursor.execute("""
            INSERT INTO sensor_telemetry (batch_id, temperature_c, humidity_rh, current_mass_g, heater_state, fan_state)
            VALUES (?, 36.0, 62.0, 1300.0, 1, 1)
        """, (test_batch,))

    res3 = fsm.evaluate_batch_state(test_batch)
    print(f"Transition: {res3['previous_state']} -> {res3['current_state']}")
    print(f"Reason:     {res3['reason']}")
    print(f"Actuator:   {res3['actuator_commands']['description']}")
    assert res3['current_state'] == READY_FOR_NEXT_BATCH, "Expected transition to READY_FOR_NEXT_BATCH"
    assert res3['actuator_commands']['heater_relay'] == 0, "Expected Heater OFF when released"

    # --- Test 4: Emergency Abort - Over-Temperature (> 58.0°C) ---
    print("\n--- Test 4: EMERGENCY ABORT - Over-Temperature (> 58.0°C) ---")
    with fsm.get_db_connection() as conn:
        cursor = conn.cursor()
        # Reset to STATE_1 for test
        cursor.execute("UPDATE batch_metadata SET current_state = 'STATE_1' WHERE batch_id = ?", (test_batch,))
        # Insert high temperature telemetry
        cursor.execute("""
            INSERT INTO sensor_telemetry (batch_id, temperature_c, humidity_rh, current_mass_g, heater_state, fan_state)
            VALUES (?, 61.5, 80.0, 4500.0, 1, 1)
        """, (test_batch,))

    res4 = fsm.evaluate_batch_state(test_batch)
    print(f"Transition: {res4['previous_state']} -> {res4['current_state']}")
    print(f"Reason:     {res4['reason']}")
    print(f"Actuator:   {res4['actuator_commands']['description']}")
    assert res4['current_state'] == STATE_E, "Expected transition to STATE_E"
    assert res4['actuator_commands']['heater_relay'] == 0, "Expected Emergency Heater CUTOFF"
    assert res4['actuator_commands']['fan_relay'] == 1, "Expected Fan MAX in Emergency"

    # --- Test 5: Emergency Abort - Mold Detected by Edge AI ---
    print("\n--- Test 5: EMERGENCY ABORT - Mold Detected ---")
    with fsm.get_db_connection() as conn:
        cursor = conn.cursor()
        # Reset to STATE_2 for test
        cursor.execute("UPDATE batch_metadata SET current_state = 'STATE_2' WHERE batch_id = ?", (test_batch,))
        # Normal temp telemetry
        cursor.execute("""
            INSERT INTO sensor_telemetry (batch_id, temperature_c, humidity_rh, current_mass_g, heater_state, fan_state)
            VALUES (?, 36.0, 65.0, 3000.0, 1, 1)
        """, (test_batch,))
        # Vision inspection detecting mold
        cursor.execute("""
            INSERT INTO vision_inspections (batch_id, tray_index, brown_ratio, mold_detected, image_path)
            VALUES (?, 1, 85.0, 1, 'mold_sample.jpg')
        """, (test_batch,))

    res5 = fsm.evaluate_batch_state(test_batch)
    print(f"Transition: {res5['previous_state']} -> {res5['current_state']}")
    print(f"Reason:     {res5['reason']}")
    print(f"Actuator:   {res5['actuator_commands']['description']}")
    assert res5['current_state'] == STATE_E, "Expected transition to STATE_E due to mold"
    assert res5['actuator_commands']['heater_relay'] == 0, "Expected Emergency Heater CUTOFF"

    print("\n=====================================================================")
    print("          ALL FSM CONTROLLER TESTS PASSED SUCCESSFULLY!              ")
    print("=====================================================================")

if __name__ == "__main__":
    run_fsm_tests()
