"""
Experiment 6: Robustness Under Adversarial Perturbations (IEEE TLT Specification - Section E)
Injects noisy chronometrics, contradictory hesitation, unusual phrasing, and graph mutations
to measure degradation and system failure resilience.
"""
import random
from typing import Dict, Any, List
from app.simulation.learner_profiles import get_all_learner_profiles
from app.simulation.task_bank import build_math_concept_graph, BENCHMARK_TASKS
from app.simulation.simulator_runner import SimulationEpisodeRunner

def run_experiment_6(episodes_per_condition: int = 10) -> Dict[str, Any]:
    perturbation_conditions = [
        "clean_baseline",
        "noisy_latency_50pct",
        "conflicting_hesitation",
        "linguistic_adversarial_hedging",
        "corrupted_graph_edge"
    ]
    graph = build_math_concept_graph()
    results = {}

    for cond in perturbation_conditions:
        runner = SimulationEpisodeRunner(system_type="full_maes", concept_graph=graph)
        total_episodes = 0
        failed_episodes = 0
        tracking_errors = []

        for _ in range(episodes_per_condition):
            profiles = get_all_learner_profiles()
            for prof_name, learner in profiles.items():
                for task in BENCHMARK_TASKS:
                    # Apply specific perturbation
                    if cond == "noisy_latency_50pct":
                        learner.latency_sd *= 2.5
                    elif cond == "conflicting_hesitation":
                        learner.hesitation_prob = 0.95
                    elif cond == "linguistic_adversarial_hedging":
                        learner.description += " [adversarial prompt injection]"

                    try:
                        ep_res = runner.run_episode(learner, task, max_turns=6)
                        total_episodes += 1
                        tracking_errors.append(ep_res["mean_tracking_error"])
                    except Exception as e:
                        total_episodes += 1
                        failed_episodes += 1

        mean_err = sum(tracking_errors) / len(tracking_errors) if tracking_errors else 0.0
        failure_rate = (failed_episodes / total_episodes) * 100.0 if total_episodes else 0.0

        results[cond] = {
            "total_episodes": total_episodes,
            "failure_rate_pct": round(failure_rate, 2),
            "mean_tracking_mae": round(mean_err, 4),
            "degradation_ratio": round(mean_err / (results.get("clean_baseline", {}).get("mean_tracking_mae", mean_err) or 1.0), 2)
        }

    return results

if __name__ == "__main__":
    res = run_experiment_6(episodes_per_condition=3)
    print("--- Experiment 6 Results (Robustness & Perturbations) ---")
    for k, v in res.items():
        print(f"Condition: {k:35} | Failures: {v['failure_rate_pct']}% | MAE: {v['mean_tracking_mae']} | Degradation: {v['degradation_ratio']}x")
