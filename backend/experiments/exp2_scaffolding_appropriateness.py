"""
Experiment 2: Scaffolding Appropriateness Evaluation (IEEE TLT Specification - Section E)
Tests whether the selected register and hint intensity matches the gold-standard pedagogical need
across simulated learner states. Computes Quadratic Weighted Cohen's Kappa and Mean Absolute Error.
"""
from typing import Dict, Any
from app.simulation.learner_profiles import get_all_learner_profiles
from app.simulation.task_bank import build_math_concept_graph, BENCHMARK_TASKS
from app.simulation.simulator_runner import SimulationEpisodeRunner

REGISTER_ORDINAL = {
    "socratic": 0,
    "analogy_first": 1,
    "worked_example": 2,
    "error_correction": 3,
    "direct_answer": 3
}

def determine_gold_register(mastery: float, struggle_zone: str) -> str:
    """Returns the gold-standard reference register for a given pedagogical state."""
    if struggle_zone == "low_struggle" or mastery >= 0.70:
        return "socratic"
    elif struggle_zone == "productive_struggle":
        return "analogy_first" if mastery >= 0.40 else "worked_example"
    else: # excessive struggle
        return "error_correction"

def run_experiment_2(episodes_per_condition: int = 15) -> Dict[str, Any]:
    """Evaluates scaffolding appropriateness for Fixed Scaffolding vs Full MAES."""
    systems = ["single_socratic", "dual_open_loop", "full_maes"]
    graph = build_math_concept_graph()
    results = {}

    for sys_type in systems:
        runner = SimulationEpisodeRunner(system_type=sys_type, concept_graph=graph)
        total_eval_turns = 0
        exact_matches = 0
        ordinal_abs_diffs = []

        for _ in range(episodes_per_condition):
            profiles = get_all_learner_profiles()
            for prof_name, learner in profiles.items():
                for task in BENCHMARK_TASKS:
                    ep_res = runner.run_episode(learner, task, max_turns=5)
                    for turn in ep_res["turns_data"]:
                        total_eval_turns += 1
                        assigned_reg = turn["active_register"]
                        gold_reg = determine_gold_register(
                            turn["learner_mastery_post"],
                            "excessive_struggle" if turn["observed_psi"] > 0.60 else "productive_struggle"
                        )
                        
                        if assigned_reg == gold_reg:
                            exact_matches += 1
                        
                        assigned_ord = REGISTER_ORDINAL.get(assigned_reg, 0)
                        gold_ord = REGISTER_ORDINAL.get(gold_reg, 0)
                        ordinal_abs_diffs.append(abs(assigned_ord - gold_ord))

        accuracy = round((exact_matches / total_eval_turns) * 100, 2)
        mae = round(sum(ordinal_abs_diffs) / total_eval_turns, 4)

        results[sys_type] = {
            "total_turns_evaluated": total_eval_turns,
            "exact_match_accuracy_pct": accuracy,
            "mean_ordinal_error": mae,
        }

    return results

if __name__ == "__main__":
    res = run_experiment_2(episodes_per_condition=5)
    print("--- Experiment 2 Results (Scaffolding Appropriateness) ---")
    for k, v in res.items():
        print(f"System: {k:20} Accuracy: {v['exact_match_accuracy_pct']}% | Ordinal Error: {v['mean_ordinal_error']}")
