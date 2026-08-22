"""
Experiment 8: Expert Pedagogical Evaluation & Blinding Export (IEEE TLT Specification - Section E)
Generates randomized, blinded sample pools of generated hints across all 4 system conditions
for human expert educator scoring, and computes Fleiss' Kappa inter-rater reliability.
"""
import os
import csv
import uuid
import random
from typing import Dict, Any, List
from app.simulation.learner_profiles import get_all_learner_profiles
from app.simulation.task_bank import build_math_concept_graph, BENCHMARK_TASKS
from app.simulation.simulator_runner import SimulationEpisodeRunner

def export_expert_evaluation_samples(
    samples_per_system: int = 25,
    output_csv_path: str = "backend/experiments/results/expert_eval_blinded_samples.csv"
) -> str:
    """
    Generates a blinded, randomized dataset of hints across all 4 systems for expert evaluation.
    """
    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
    systems = ["direct_llm", "single_socratic", "dual_open_loop", "full_maes"]
    graph = build_math_concept_graph()
    
    blinded_records = []
    key_mapping = []

    for sys_type in systems:
        runner = SimulationEpisodeRunner(system_type=sys_type, concept_graph=graph)
        collected = 0
        
        while collected < samples_per_system:
            profiles = get_all_learner_profiles()
            for prof_name, learner in profiles.items():
                for task in BENCHMARK_TASKS:
                    if collected >= samples_per_system:
                        break
                    ep_res = runner.run_episode(learner, task, max_turns=3)
                    turn_data = ep_res["turns_data"][-1]
                    
                    sample_id = f"SMP-{uuid.uuid4().hex[:8].upper()}"
                    blinded_records.append({
                        "sample_id": sample_id,
                        "domain": task["domain"],
                        "task_prompt": task["prompt"],
                        "student_message": turn_data["student_message"],
                        "tutor_hint_to_evaluate": turn_data["generated_hint"],
                        "rater_score_appropriateness_1to5": "",
                        "rater_score_non_leakage_1to5": "",
                        "rater_score_correctness_1to5": "",
                        "rater_score_bloom_align_1to5": "",
                        "rater_notes": ""
                    })
                    key_mapping.append({
                        "sample_id": sample_id,
                        "true_system": sys_type,
                        "learner_profile": prof_name,
                        "task_id": task["task_id"]
                    })
                    collected += 1

    # Randomize blinded records so raters cannot infer condition ordering
    random.shuffle(blinded_records)

    # Write evaluation CSV for educators
    with open(output_csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(blinded_records[0].keys()))
        writer.writeheader()
        writer.writerows(blinded_records)

    # Write key mapping separately
    key_path = output_csv_path.replace(".csv", "_decoding_key.csv")
    with open(key_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(key_mapping[0].keys()))
        writer.writeheader()
        writer.writerows(key_mapping)

    return output_csv_path

def compute_fleiss_kappa(ratings_matrix: List[List[int]], num_categories: int = 5) -> float:
    """
    Computes Fleiss' Kappa for inter-rater agreement across N subjects and k raters.
    Ratings matrix: shape (N subjects, num_categories), where cell [i][j] is the count of raters assigning category j to subject i.
    """
    N = len(ratings_matrix)
    if N == 0:
        return 0.0
    n = sum(ratings_matrix[0]) # total raters per subject
    if n <= 1:
        return 1.0

    # Proportion of all assignments to category j
    p_j = [sum(ratings_matrix[i][j] for i in range(N)) / (N * n) for j in range(num_categories)]

    # Extent of agreement for subject i
    P_i = [
        (sum(ratings_matrix[i][j]**2 for j in range(num_categories)) - n) / (n * (n - 1))
        for i in range(N)
    ]

    P_bar = sum(P_i) / N
    P_e = sum(p**2 for p in p_j)

    if (1.0 - P_e) == 0:
        return 1.0
    kappa = (P_bar - P_e) / (1.0 - P_e)
    return round(kappa, 4)

if __name__ == "__main__":
    path = export_expert_evaluation_samples(samples_per_system=5)
    print(f"--- Experiment 8 Blinded Sample Export Complete: {path} ---")
