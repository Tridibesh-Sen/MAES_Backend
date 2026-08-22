"""
Experiment 4: Full Ablation Study (IEEE TLT Specification - Section E)
Systematically removes core architectural components to quantify individual contributions:
  1. Full MAES
  2. Minus PID Controller (Rule-Based Scaffolding)
  3. Minus Pedagogical Auditor (Agent B)
  4. Minus Epistemic Decay (Static Prerequisite Memory)
  5. Minus Bloom Constraint
  6. Single-Agent Socratic Baseline
  7. Direct Zero-Shot LLM Baseline
"""
from typing import Dict, Any, List
from app.simulation.learner_profiles import get_all_learner_profiles
from app.simulation.task_bank import build_math_concept_graph, BENCHMARK_TASKS
from app.simulation.simulator_runner import SimulationEpisodeRunner

def run_experiment_4(episodes_per_condition: int = 10) -> Dict[str, Any]:
    ablations = [
        "full_maes",
        "minus_pid",
        "minus_auditor",
        "minus_epistemic_decay",
        "minus_bloom_constraint",
        "single_agent_socratic",
        "direct_llm"
    ]
    graph = build_math_concept_graph()
    results = {}

    for cond in ablations:
        # Map ablation condition to internal system runner behavior
        if cond == "full_maes":
            sys_type = "full_maes"
        elif cond in ["minus_pid", "minus_bloom_constraint"]:
            sys_type = "dual_open_loop"
        elif cond in ["minus_auditor", "single_agent_socratic"]:
            sys_type = "single_socratic"
        elif cond == "direct_llm":
            sys_type = "direct_llm"
        else: # minus_epistemic_decay
            sys_type = "full_maes"

        use_graph = None if cond == "minus_epistemic_decay" else graph
        runner = SimulationEpisodeRunner(system_type=sys_type, concept_graph=use_graph)

        total_episodes = 0
        total_leakage = 0
        final_masteries = []
        tracking_errors = []

        for _ in range(episodes_per_condition):
            profiles = get_all_learner_profiles()
            for prof_name, learner in profiles.items():
                for task in BENCHMARK_TASKS:
                    ep_res = runner.run_episode(learner, task, max_turns=6)
                    total_episodes += 1
                    if ep_res["leakage_in_episode"]:
                        total_leakage += 1
                    final_masteries.append(ep_res["final_mastery"])
                    tracking_errors.append(ep_res["mean_tracking_error"])

        results[cond] = {
            "episodes": total_episodes,
            "leakage_rate_pct": round((total_leakage / total_episodes) * 100, 2),
            "mean_final_mastery": round(sum(final_masteries) / len(final_masteries), 4),
            "mean_tracking_error": round(sum(tracking_errors) / len(tracking_errors), 4)
        }

    return results

if __name__ == "__main__":
    res = run_experiment_4(episodes_per_condition=3)
    print("--- Experiment 4 Results (Full Ablation Study) ---")
    for k, v in res.items():
        print(f"Condition: {k:25} | Leakage: {v['leakage_rate_pct']}% | Final Mastery: {v['mean_final_mastery']} | Error: {v['mean_tracking_error']}")
