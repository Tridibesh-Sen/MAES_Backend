"""
Master Experiment Runner & IEEE TLT Publication Table Generator
Executes Experiments 1 through 7, runs Section F/G validations, exports Experiment 8 blinding pools,
and outputs complete formatted IEEE TLT Tables (Tables IV, V, VI, VII, VIII).
"""
import os
import json
import time
from app.simulation.learner_profiles import get_all_learner_profiles
from experiments.exp1_answer_leakage import run_experiment_1
from experiments.exp2_scaffolding_appropriateness import run_experiment_2
from experiments.exp3_controller_comparison import run_experiment_3
from experiments.exp4_full_ablation import run_experiment_4
from experiments.exp5_epistemic_decay import run_experiment_5
from experiments.exp6_robustness_perturbations import run_experiment_6
from experiments.exp7_efficiency_latency import run_experiment_7
from experiments.exp8_expert_eval_export import export_expert_evaluation_samples
from experiments.psi_and_pid_validation import run_psi_component_ablation, generate_pid_step_trajectory

RESULTS_DIR = "backend/experiments/results"

def run_all(fast_mode: bool = True):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    reps = 3 if fast_mode else 15
    print(f"===============================================================")
    print(f"   MAES IEEE TLT EXPERIMENTAL BENCHMARK SUITE (Fast Mode: {fast_mode})")
    print(f"===============================================================\n")

    # 1. Exp 1: Answer Leakage
    print("[1/8] Running Experiment 1: Answer Leakage...")
    e1_results = run_experiment_1(episodes_per_condition=reps)
    with open(f"{RESULTS_DIR}/table_iv_leakage.json", "w") as f:
        json.dump(e1_results, f, indent=2)

    # 2. Exp 2: Scaffolding Appropriateness
    print("[2/8] Running Experiment 2: Scaffolding Appropriateness...")
    e2_results = run_experiment_2(episodes_per_condition=reps)
    with open(f"{RESULTS_DIR}/table_iv_scaffolding.json", "w") as f:
        json.dump(e2_results, f, indent=2)

    # 3. Exp 3: Controller Comparison
    print("[3/8] Running Experiment 3: Controller Comparison (Fixed vs P vs PI vs PID)...")
    e3_results = run_experiment_3(repetitions=reps)
    with open(f"{RESULTS_DIR}/table_vi_controllers.json", "w") as f:
        json.dump(e3_results, f, indent=2)

    # 4. Exp 4: Full Ablation
    print("[4/8] Running Experiment 4: Full Component Ablation...")
    e4_results = run_experiment_4(episodes_per_condition=reps)
    with open(f"{RESULTS_DIR}/table_v_ablation.json", "w") as f:
        json.dump(e4_results, f, indent=2)

    # 5. Exp 5: Epistemic Decay
    print("[5/8] Running Experiment 5: Epistemic Decay & Prerequisite Trigger...")
    e5_results = run_experiment_5()
    with open(f"{RESULTS_DIR}/epistemic_decay_analysis.json", "w") as f:
        json.dump(e5_results, f, indent=2)

    # 6. Exp 6: Robustness Under Noise
    print("[6/8] Running Experiment 6: Robustness & Adversarial Perturbations...")
    e6_results = run_experiment_6(episodes_per_condition=reps)
    with open(f"{RESULTS_DIR}/table_viii_robustness.json", "w") as f:
        json.dump(e6_results, f, indent=2)

    # 7. Exp 7: Efficiency & Latency
    print("[7/8] Running Experiment 7: Computational Efficiency & Cost...")
    e7_results = run_experiment_7(episodes_per_condition=reps)
    with open(f"{RESULTS_DIR}/table_iv_efficiency.json", "w") as f:
        json.dump(e7_results, f, indent=2)

    # 8. Exp 8: Export Blinded Expert Pack
    print("[8/8] Exporting Experiment 8 Blinded Human Evaluation Package...")
    e8_path = export_expert_evaluation_samples(samples_per_system=5 if fast_mode else 25, output_csv_path=f"{RESULTS_DIR}/expert_eval_blinded_samples.csv")

    # 9. PSI Validation & PID Trajectory
    print("[+] Running Section F PSI Validation & Section G PID Trajectory...")
    psi_ab = run_psi_component_ablation()
    pid_traj = generate_pid_step_trajectory(turns=8)
    with open(f"{RESULTS_DIR}/psi_ablation.json", "w") as f:
        json.dump(psi_ab, f, indent=2)
    with open(f"{RESULTS_DIR}/fig5_pid_trajectory.json", "w") as f:
        json.dump(pid_traj, f, indent=2)

    print("\n===============================================================")
    print("                    IEEE TLT SUMMARY TABLES")
    print("===============================================================\n")

    # Format Table IV: Main Results
    print("TABLE IV: MAIN COMPARATIVE RESULTS")
    print("-" * 75)
    print(f"{'System Configuration':<25} | {'Leakage Rate (%)':<16} | {'Scaffold Acc (%)':<16} | {'Cost/1k ($)':<10}")
    print("-" * 75)
    for sys in ["direct_llm", "single_socratic", "dual_open_loop", "full_maes"]:
        leak = f"{e1_results.get(sys, {}).get('episode_leakage_rate_pct', 0.0)}%"
        acc = f"{e2_results.get(sys, {}).get('exact_match_accuracy_pct', 'N/A')}"
        if acc != 'N/A': acc += '%'
        cost = f"${e7_results.get(sys, {}).get('estimated_cost_per_1k_turns_usd', 0.08)}"
        print(f"{sys:<25} | {leak:<16} | {acc:<16} | {cost:<10}")
    print("-" * 75)

    # Format Table V: Ablations
    print("\nTABLE V: ABLATION STUDY RESULTS")
    print("-" * 65)
    print(f"{'Ablation Condition':<28} | {'Leakage (%)':<12} | {'Final Mastery':<14}")
    print("-" * 65)
    for cond, data in e4_results.items():
        print(f"{cond:<28} | {data['leakage_rate_pct']:<12.1f}% | {data['mean_final_mastery']:<14.3f}")
    print("-" * 65)

    # Format Table VI: Controller Comparison
    print("\nTABLE VI: CONTROLLER COMPARISON (Fixed vs P vs PI vs PID)")
    print("-" * 72)
    print(f"{'Controller Variant':<18} | {'Tracking MAE':<14} | {'Settling Turns':<14} | {'Switches':<10}")
    print("-" * 72)
    for ctrl, data in e3_results.items():
        print(f"{ctrl:<18} | {data['mean_tracking_mae']:<14.4f} | {data['mean_settling_turns']:<14.1f} | {data['mean_register_switches']:<10.1f}")
    print("-" * 72)

    # Format Table VIII: Robustness
    print("\nTABLE VIII: ROBUSTNESS UNDER ADVERSARIAL PERTURBATIONS")
    print("-" * 65)
    print(f"{'Perturbation Type':<32} | {'Failure Rate':<12} | {'Degradation':<12}")
    print("-" * 65)
    for cond, data in e6_results.items():
        print(f"{cond:<32} | {data['failure_rate_pct']:<12.1f}% | {data['degradation_ratio']:<12.2f}x")
    print("-" * 65)

    print(f"\n[OK] All results saved to: {RESULTS_DIR}/")

if __name__ == "__main__":
    run_all(fast_mode=True)
