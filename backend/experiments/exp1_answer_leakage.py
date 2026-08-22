"""
Experiment 1: Answer Leakage Evaluation (IEEE TLT Specification - Section E)
Compares Answer Leakage rates across:
  1. Direct LLM
  2. Single-Agent Socratic (No Auditor)
  3. Dual-Agent Open-Loop (No closed-loop controller)
  4. Full MAES (Closed-Loop PID + Auditor)
Reports leakage percentages with 95% Wilson score confidence intervals.
"""
import math
from typing import Dict, Any, List
from app.simulation.learner_profiles import get_all_learner_profiles
from app.simulation.task_bank import build_math_concept_graph, BENCHMARK_TASKS
from app.simulation.simulator_runner import SimulationEpisodeRunner

def wilson_score_interval(k: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Calculates Wilson score interval for binomial proportions."""
    if n == 0:
        return 0.0, 0.0
    z = 1.95996 # 95% confidence z-score
    p = k / n
    denom = 1 + (z**2 / n)
    center = (p + (z**2 / (2 * n))) / denom
    margin = (z * math.sqrt((p * (1 - p) / n) + (z**2 / (4 * (n**2))))) / denom
    low = max(0.0, center - margin)
    high = min(1.0, center + margin)
    return round(low * 100, 2), round(high * 100, 2)

def run_experiment_1(episodes_per_condition: int = 20) -> Dict[str, Any]:
    """Runs Experiment 1 over all 4 system conditions."""
    systems = ["direct_llm", "single_socratic", "dual_open_loop", "full_maes"]
    graph = build_math_concept_graph()
    results = {}

    for sys_type in systems:
        runner = SimulationEpisodeRunner(system_type=sys_type, concept_graph=graph)
        total_episodes = 0
        leaked_episodes = 0
        total_turns = 0
        leaked_turns = 0

        for _ in range(episodes_per_condition):
            profiles = get_all_learner_profiles()
            for prof_name, learner in profiles.items():
                for task in BENCHMARK_TASKS:
                    ep_res = runner.run_episode(learner, task, max_turns=6)
                    total_episodes += 1
                    if ep_res["leakage_in_episode"]:
                        leaked_episodes += 1
                    
                    for turn in ep_res["turns_data"]:
                        total_turns += 1
                        if turn["leakage_occurred"]:
                            leaked_turns += 1

        ep_rate = round((leaked_episodes / total_episodes) * 100, 2)
        turn_rate = round((leaked_turns / total_turns) * 100, 2)
        low_ci, high_ci = wilson_score_interval(leaked_episodes, total_episodes)

        results[sys_type] = {
            "total_episodes": total_episodes,
            "leaked_episodes": leaked_episodes,
            "episode_leakage_rate_pct": ep_rate,
            "wilson_ci_95": (low_ci, high_ci),
            "total_turns": total_turns,
            "turn_leakage_rate_pct": turn_rate
        }

    return results

if __name__ == "__main__":
    res = run_experiment_1(episodes_per_condition=5)
    print("--- Experiment 1 Results (Answer Leakage) ---")
    for k, v in res.items():
        print(f"System: {k:20} Leakage: {v['episode_leakage_rate_pct']}% (95% CI: {v['wilson_ci_95'][0]}% - {v['wilson_ci_95'][1]}%)")
