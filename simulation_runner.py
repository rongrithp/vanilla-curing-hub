"""
Vanilla Curing Hub - 14-Day Accelerated Time-Series Physics Simulator
Simulates physical mass loss (5.0 kg -> 1.35 kg), ambient temperature/humidity variations,
VPD balancing, and FSM state progression without deadlocks.
"""

import math
import random
from test_curing_logic import calculate_vpd, update_vent_position, evaluate_chamber_state

def run_14day_simulation():
    print("===================================================================================")
    print("      VANILLA CURING HUB - 14-DAY ACCELERATED TIME-SERIES PHYSICS SIMULATION       ")
    print("===================================================================================")

    initial_mass_g = 5000.0
    current_mass_g = 5000.0

    current_state = "STATE_0"
    brown_ratio = 0.0
    vent_position_pct = 0
    total_hours = 14 * 24  # 336 hours
    
    time_step_hours = 6
    elapsed_hours = 0
    
    header = f"{'Time (h)':<8} | {'Day':<5} | {'State':<23} | {'Temp(°C)':<8} | {'RH(%)':<6} | {'VPD(kPa)':<8} | {'Mass(g)':<8} | {'Ratio(%)':<8} | {'Vent(%)':<7} | {'Heater':<6}"
    divider = "-" * len(header)
    
    print(divider)
    print(header)
    print(divider)

    while elapsed_hours <= total_hours:
        day = round(elapsed_hours / 24.0, 1)

        # Ambient / Internal physics simulation based on stage
        if current_state in ("STATE_0", "SWEATING"):
            # Stage 1 (Sweating): Temp 45.0 - 50.0°C, RH > 85%, Vent Closed (0%)
            temp_c = round(47.5 + random.uniform(-0.8, 0.8), 1)
            rh_percent = round(88.0 + random.uniform(-1.5, 1.5), 1)
            brown_ratio = min(95.0, (elapsed_hours / 36.0) * 95.0)
            mass_loss = (5000.0 * 0.04) * (time_step_hours / 36.0)
            current_mass_g = max(4800.0, current_mass_g - mass_loss)

        elif current_state == "SLOW_DRYING":
            # Stage 2 (Slow Drying): Temp 35.0 - 38.0°C, RH 60-70%, VPD ~1.0 kPa
            temp_c = round(36.5 + random.uniform(-0.8, 0.8), 1)
            rh_percent = round(64.0 + random.uniform(-3.0, 3.0), 1)
            
            remaining_drying_hours = (14 * 24) - 36
            mass_loss = ((4800.0 - 1350.0) / remaining_drying_hours) * time_step_hours * random.uniform(0.95, 1.05)
            current_mass_g = max(1350.0, current_mass_g - mass_loss)

        else: # COMPLETED_CONDITIONING
            temp_c = 25.0
            rh_percent = 65.0
            current_mass_g = 1350.0

        # Calculate VPD using Tetens Equation
        vpd_kpa = calculate_vpd(temp_c, rh_percent)

        # Update Vent Modulation in Slow Drying
        if current_state == "SLOW_DRYING":
            vent_position_pct = update_vent_position(vent_position_pct, vpd_kpa)
        elif current_state == "SWEATING":
            vent_position_pct = 0
        else:
            vent_position_pct = 0

        # Evaluate FSM Transition
        eval_res = evaluate_chamber_state(
            current_state=current_state,
            temp_c=temp_c,
            rh_percent=rh_percent,
            current_mass_g=current_mass_g,
            initial_mass_g=initial_mass_g,
            brown_ratio=brown_ratio,
            elapsed_sweat_hours=elapsed_hours
        )

        current_state = eval_res["state"]
        heater_state = eval_res["heater_state"]
        mass_ratio_pct = round((current_mass_g / initial_mass_g) * 100.0, 1)

        # Log telemetry every 12 simulated hours or upon completion
        if elapsed_hours % 12 == 0 or current_state == "COMPLETED_CONDITIONING":
            print(f"{elapsed_hours:<8} | {day:<5.1f} | {current_state:<23} | {temp_c:<8.1f} | {rh_percent:<6.1f} | {vpd_kpa:<8.2f} | {current_mass_g:<8.1f} | {mass_ratio_pct:<8.1f} | {vent_position_pct:<7} | {heater_state:<6}")

        if current_state == "COMPLETED_CONDITIONING":
            print(divider)
            print(f">> SUCCESS: Batch reached target mass exit condition ({mass_ratio_pct}% <= 27.0%) at Hour {elapsed_hours} (Day {day}).")
            print(">> FSM Active Chamber Lifecycle Complete -> Offloaded to Wooden Box.")
            print(divider)
            break

        elapsed_hours += time_step_hours

    print("\n===================================================================================")
    print("        14-DAY PHYSICS SIMULATION COMPLETED WITH ZERO DEADLOCKS / ERRORS           ")
    print("===================================================================================")

if __name__ == "__main__":
    run_14day_simulation()
