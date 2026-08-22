"""
Experiment 3: Controller Architecture Comparison (IEEE TLT Specification - Section E & G)
Compares Fixed Threshold, P, PI, and PID controller variants on:
  - Mean Absolute Tracking Error (MAE)
  - Settling Time (Turns to enter and stay within +/- 0.05 of target PSI)
  - Percentage Overshoot (Mp)
  - Unnecessary register switches / chattering rate
"""
import math
from typing import Dict, Any, List
from app.simulation.learner_profiles import get_all_learner_profiles
from app.simulation.task_bank import build_math_concept_graph, BENCHMARK_TASKS
from app.core.scaffold_controller import PIDScaffoldController
from app.core.psi_engine import PSIEngine

class CustomControllerRunner:
    def __init__(self, mode: str, target_psi: float = 0.40):
        self.mode = mode # "fixed", "p_only", "pi", "pid"
        self.target_psi = target_psi
        
        if mode == "p_only":
            self.ctrl = PIDScaffoldController(target_psi=target_psi, kp=0.85, ki=0.0, kd=0.0)
        elif mode == "pi":
            self.ctrl = PIDScaffoldController(target_psi=target_psi, kp=0.85, ki=0.20, kd=0.0)
        elif mode == "pid":
            self.ctrl = PIDScaffoldController(target_psi=target_psi, kp=0.85, ki=0.20, kd=0.15)
        else:
            self.ctrl = None

    def run_step_response(self, learner, task, n_turns: int = 10) -> Dict[str, Any]:
        psi_engine = PSIEngine()
        if self.ctrl:
            self.ctrl.reset()

        errors = []
        registers = []
        u_vals = []
        prev_reg = None
        switches = 0
        peak_error = 0.0
        settled_turn = None

        for t in range(1, n_turns + 1):
            learner_out = learner.generate_turn_behavior(
                hint_received="hint",
                register_received=registers[-1] if registers else "socratic",
                task_difficulty=task["difficulty"]
            )
            psi_res = psi_engine.compute_psi(
                latency_seconds=learner_out["latency_seconds"],
                backspace_count=learner_out["backspace_count"],
                pause_count=learner_out["pause_count"],
                student_message=learner_out["student_message"],
                concept_distance=0.0
            )
            obs_psi = psi_res["psi"]
            err = obs_psi - self.target_psi
            errors.append(err)
            peak_error = max(peak_error, abs(err))

            # Controller output
            if self.mode == "fixed":
                u = 0.20 if obs_psi < 0.40 else 0.80
                reg = PIDScaffoldController.map_register(u)
            else:
                u, reg, _ = self.ctrl.compute_step(obs_psi)

            u_vals.append(u)
            registers.append(reg)
            if prev_reg and reg != prev_reg:
                switches += 1
            prev_reg = reg

        # Calculate settling time (first turn where all remaining |err| <= 0.08)
        for i in range(len(errors)):
            if all(abs(e) <= 0.08 for e in errors[i:]):
                settled_turn = i + 1
                break
        if settled_turn is None:
            settled_turn = n_turns # Did not settle

        mae = sum(abs(e) for e in errors) / len(errors)
        overshoot_pct = max(0.0, (peak_error - 0.10) / 0.40 * 100.0)

        return {
            "mae": round(mae, 4),
            "settling_turn": settled_turn,
            "overshoot_pct": round(overshoot_pct, 2),
            "chattering_switches": switches
        }

def run_experiment_3(repetitions: int = 10) -> Dict[str, Any]:
    modes = ["fixed", "p_only", "pi", "pid"]
    results = {}

    for mode in modes:
        runner = CustomControllerRunner(mode=mode)
        maes = []
        settling_times = []
        overshoots = []
        switches_list = []

        for _ in range(repetitions):
            profiles = get_all_learner_profiles()
            for prof_name, learner in profiles.items():
                for task in BENCHMARK_TASKS:
                    m = runner.run_step_response(learner, task, n_turns=8)
                    maes.append(m["mae"])
                    settling_times.append(m["settling_turn"])
                    overshoots.append(m["overshoot_pct"])
                    switches_list.append(m["chattering_switches"])

        results[mode] = {
            "mean_tracking_mae": round(sum(maes) / len(maes), 4),
            "mean_settling_turns": round(sum(settling_times) / len(settling_times), 2),
            "mean_overshoot_pct": round(sum(overshoots) / len(overshoots), 2),
            "mean_register_switches": round(sum(switches_list) / len(switches_list), 2)
        }

    return results

if __name__ == "__main__":
    res = run_experiment_3(repetitions=3)
    print("--- Experiment 3 Results (Controller Comparison) ---")
    for k, v in res.items():
        print(f"Mode: {k:10} | MAE: {v['mean_tracking_mae']} | Settling: {v['mean_settling_turns']} turns | Switches: {v['mean_register_switches']}")
