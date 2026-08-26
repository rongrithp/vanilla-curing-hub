"""
Vanilla Curing Hub - Unit Test Suite
Verifies Tetens VPD formula calculation, Decoupled Vent Modulation, FSM State Exit Conditions, and Safety Watchdog Tripping.
"""

import math
import unittest
from typing import Dict, Any

# Tetens Formula Helper
def calculate_vpd(temp_c: float, rh_percent: float) -> float:
    if math.isnan(temp_c) or math.isnan(rh_percent):
        return 0.0
    if temp_c < -20.0 or rh_percent >= 100.0:
        return 0.0
    if rh_percent <= 0.0:
        es = 0.61078 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
        return round(es, 2)
    es = 0.61078 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
    ea = es * (rh_percent / 100.0)
    vpd = es - ea
    return round(max(0.0, vpd), 2)

# Decoupled Vent Control Helper
def update_vent_position(current_vent_percent: int, vpd_kpa: float, min_deadband: float = 0.9, max_deadband: float = 1.1) -> int:
    if vpd_kpa < min_deadband:
        # Air too humid -> open vent step to increase drying
        return min(100, current_vent_percent + 10)
    elif vpd_kpa > max_deadband:
        # Air too dry -> close vent step to retain moisture
        return max(0, current_vent_percent - 10)
    else:
        # Within deadband -> hold current position
        return current_vent_percent

# FSM & Safety Logic Helper
def evaluate_chamber_state(
    current_state: str,
    temp_c: float,
    rh_percent: float,
    current_mass_g: float,
    initial_mass_g: float = 5000.0,
    brown_ratio: float = 0.0,
    elapsed_sweat_hours: float = 0.0,
    mold_detected: bool = False
) -> Dict[str, Any]:
    # Watchdog Emergency Check (Triggers on over-temp >= 58.0°C, NaN/sensor fault, or mold detection)
    if math.isnan(temp_c) or math.isnan(rh_percent) or temp_c >= 58.0 or mold_detected:
        return {
            "state": "EMERGENCY_SAFE_MODE",
            "heater_state": 0,       # CUTOFF
            "fan_state": 1,          # MAX PURGE
            "vent_position_pct": 100 # FULLY OPEN
        }

    mass_ratio = (current_mass_g / initial_mass_g) if initial_mass_g > 0 else 1.0

    if current_state == "STATE_0":
        return {"state": "SWEATING", "heater_state": 1, "fan_state": 1, "vent_position_pct": 0}

    elif current_state == "SWEATING":
        if brown_ratio >= 90.0 and elapsed_sweat_hours >= 24.0:
            return {"state": "SLOW_DRYING", "heater_state": 1, "fan_state": 1, "vent_position_pct": 30}
        return {"state": "SWEATING", "heater_state": 1, "fan_state": 1, "vent_position_pct": 0}

    elif current_state == "SLOW_DRYING":
        if mass_ratio <= 0.27:
            return {"state": "COMPLETED_CONDITIONING", "heater_state": 0, "fan_state": 0, "vent_position_pct": 0}
        return {"state": "SLOW_DRYING", "heater_state": 1, "fan_state": 1, "vent_position_pct": 50}

    return {"state": current_state, "heater_state": 0, "fan_state": 0, "vent_position_pct": 0}


class TestCuringLogic(unittest.TestCase):

    def test_vpd_calculation(self):
        """Test Case 1: Tetens VPD calculation and boundary conditions."""
        # 1. Standard operating point: T = 36.0°C, RH = 65.0% -> VPD ≈ 2.08 kPa
        vpd = calculate_vpd(36.0, 65.0)
        self.assertAlmostEqual(vpd, 2.08, delta=0.05)

        # 2. Edge Case: 100% RH -> 0.0 kPa (saturated)
        self.assertEqual(calculate_vpd(35.0, 100.0), 0.0)

        # 3. Edge Case: 0% RH -> Full saturation pressure
        vpd_dry = calculate_vpd(35.0, 0.0)
        self.assertGreater(vpd_dry, 5.0)

        # 4. Temperature bounds
        self.assertEqual(calculate_vpd(-25.0, 50.0), 0.0)

    def test_decoupled_vent_control(self):
        """Test Case 2: Stepwise Vent Modulation with Hysteresis Deadband [0.9, 1.1] kPa."""
        initial_vent = 50

        # 1. Too humid (VPD = 0.7 kPa < 0.9) -> Vent opens (+10%)
        new_vent_humid = update_vent_position(initial_vent, 0.7)
        self.assertEqual(new_vent_humid, 60)

        # 2. Too dry (VPD = 1.4 kPa > 1.1) -> Vent closes (-10%)
        new_vent_dry = update_vent_position(initial_vent, 1.4)
        self.assertEqual(new_vent_dry, 40)

        # 3. In Deadband (VPD = 1.0 kPa in [0.9, 1.1]) -> Vent position unchanged
        new_vent_optimal = update_vent_position(initial_vent, 1.0)
        self.assertEqual(new_vent_optimal, 50)

    def test_mass_ratio_exit_condition(self):
        """Test Case 3: FSM State Exit Condition based on Mass Remaining Ratio."""
        initial_mass = 5000.0

        # 1. Mass = 2000g (40% remaining) -> Remains in SLOW_DRYING
        res_40pct = evaluate_chamber_state("SLOW_DRYING", 36.5, 65.0, current_mass_g=2000.0, initial_mass_g=initial_mass)
        self.assertEqual(res_40pct["state"], "SLOW_DRYING")
        self.assertEqual(res_40pct["heater_state"], 1)

        # 2. Mass = 1350g (27% remaining target) -> Transitions to COMPLETED_CONDITIONING
        res_27pct = evaluate_chamber_state("SLOW_DRYING", 36.5, 65.0, current_mass_g=1350.0, initial_mass_g=initial_mass)
        self.assertEqual(res_27pct["state"], "COMPLETED_CONDITIONING")
        self.assertEqual(res_27pct["heater_state"], 0) # Heater turned off upon completion

    def test_safety_watchdog(self):
        """Test Case 4: Hardware & Software Safety Watchdog Tripping."""
        # 1. Over-temperature injection: T = 58.5°C -> EMERGENCY_SAFE_MODE
        res_overtemp = evaluate_chamber_state("SLOW_DRYING", temp_c=58.5, rh_percent=60.0, current_mass_g=3000.0)
        self.assertEqual(res_overtemp["state"], "EMERGENCY_SAFE_MODE")
        self.assertEqual(res_overtemp["heater_state"], 0)
        self.assertEqual(res_overtemp["fan_state"], 1)
        self.assertEqual(res_overtemp["vent_position_pct"], 100)

        # 2. Sensor Fault injection: Temp = NaN -> EMERGENCY_SAFE_MODE
        res_sensor_fault = evaluate_chamber_state("SLOW_DRYING", temp_c=float("nan"), rh_percent=60.0, current_mass_g=3000.0)
        self.assertEqual(res_sensor_fault["state"], "EMERGENCY_SAFE_MODE")
        self.assertEqual(res_sensor_fault["heater_state"], 0)
        self.assertEqual(res_sensor_fault["fan_state"], 1)
        self.assertEqual(res_sensor_fault["vent_position_pct"], 100)


if __name__ == "__main__":
    unittest.main()
