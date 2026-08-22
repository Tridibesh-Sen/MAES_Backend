"""
PSI Validation & PID Trajectory Analysis (IEEE TLT Specification - Section F & G)
Fulfills:
  - Section F: PSI component ablation (L only, H only, D only, pairwise, full) and alpha/beta/gamma sensitivity.
  - Section G: Discrete-time PID step response trajectory and operational stability verification.
"""
from typing import Dict, Any, List
from app.core.psi_engine import PSIEngine
from app.core.scaffold_controller import PIDScaffoldController
from app.simulation.learner_profiles import get_all_learner_profiles
from app.simulation.task_bank import build_math_concept_graph, BENCHMARK_TASKS
from app.simulation.simulator_runner import SimulationEpisodeRunner

def run_psi_component_ablation() -> Dict[str, Any]:
    """
    Evaluates classification ability of individual PSI components against gold struggle zones.
    """
    configurations = {
        "latency_only": (1.0, 0.0, 0.0),
        "hesitation_only": (0.0, 1.0, 0.0),
        "distance_only": (0.0, 0.0, 1.0),
        "latency_plus_hesitation": (0.55, 0.45, 0.0),
        "latency_plus_distance": (0.60, 0.0, 0.40),
        "hesitation_plus_distance": (0.0, 0.60, 0.40),
        "full_composite_psi": (0.40, 0.35, 0.25)
    }

    profiles = get_all_learner_profiles()
    results = {}

    for name, (a, b, g) in configurations.items():
        engine = PSIEngine(alpha=a, beta=b, gamma=g)
        correct_classifications = 0
        total_samples = 0

        for prof_name, learner in profiles.items():
            gold_zone = "low_struggle" if "high_mastery" in prof_name else ("excessive_struggle" if "struggle" in prof_name else "productive_struggle")
            
            for _ in range(50):
                bh = learner.generate_turn_behavior()
                res = engine.compute_psi(
                    latency_seconds=bh["latency_seconds"],
                    backspace_count=bh["backspace_count"],
                    pause_count=bh["pause_count"],
                    student_message=bh["student_message"],
                    concept_distance=0.35 if "forgotten" in prof_name else 0.0
                )
                if res["zone"] == gold_zone:
                    correct_classifications += 1
                total_samples += 1

        accuracy = round((correct_classifications / total_samples) * 100, 2)
        results[name] = {
            "weights": {"alpha": a, "beta": b, "gamma": g},
            "accuracy_pct": accuracy
        }

    return results

def generate_pid_step_trajectory(turns: int = 12) -> List[Dict[str, Any]]:
    """
    Generates step-response trajectory demonstrating PID convergence to target PSI.
    """
    controller = PIDScaffoldController(target_psi=0.40, kp=0.85, ki=0.20, kd=0.15)
    profiles = get_all_learner_profiles()
    learner = profiles["persistent_struggle"] # Test on most demanding learner
    task = BENCHMARK_TASKS[0]
    psi_engine = PSIEngine()

    trajectory = []
    hint = None
    reg = "socratic"

    for t in range(1, turns + 1):
        bh = learner.generate_turn_behavior(hint_received=hint, register_received=reg, task_difficulty=task["difficulty"])
        psi_res = psi_engine.compute_psi(
            latency_seconds=bh["latency_seconds"],
            backspace_count=bh["backspace_count"],
            pause_count=bh["pause_count"],
            student_message=bh["student_message"],
            concept_distance=0.2
        )
        obs_psi = psi_res["psi"]
        u, reg, telem = controller.compute_step(obs_psi)
        hint = f"Scaffold at level {reg}"

        trajectory.append({
            "turn": t,
            "target_psi": 0.40,
            "observed_psi": obs_psi,
            "control_signal_u": round(u, 4),
            "error": round(telem["error"], 4),
            "p_term": round(telem["p_term"], 4),
            "i_term": round(telem["i_term"], 4),
            "d_term": round(telem["d_term"], 4),
            "active_register": reg,
            "stable": controller.is_stable(window=3, tolerance=0.12)
        })

    return trajectory

if __name__ == "__main__":
    print("--- Section F: PSI Component Ablation ---")
    ab_res = run_psi_component_ablation()
    for k, v in ab_res.items():
        print(f"Config: {k:30} | Accuracy: {v['accuracy_pct']}%")

    print("\n--- Section G: PID Trajectory Sample ---")
    traj = generate_pid_step_trajectory(turns=6)
    for row in traj:
        print(f"Turn {row['turn']:2} | Target: {row['target_psi']} | Obs PSI: {row['observed_psi']:.2f} | u[k]: {row['control_signal_u']:.2f} | Reg: {row['active_register']:16} | Stable: {row['stable']}")
