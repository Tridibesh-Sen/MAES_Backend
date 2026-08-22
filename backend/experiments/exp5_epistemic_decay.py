"""
Experiment 5: Epistemic Decay & Diagnostic Review Sensitivity (IEEE TLT Specification - Section E)
Evaluates exponential prerequisite memory decay across varying elapsed times (1 to 30 days)
and tests the diagnostic review trigger sensitivity and accuracy.
"""
import datetime
from typing import Dict, Any, List
from app.core.epistemic_graph import EpistemicConceptGraph

def run_experiment_5() -> Dict[str, Any]:
    elapsed_days_grid = [1, 3, 7, 14, 21, 30]
    initial_mastery_levels = [0.90, 0.75, 0.60, 0.45]
    decay_rates = [0.03, 0.05, 0.08] # Low, Medium, Fast forgetting
    results = {}

    for rate in decay_rates:
        rate_key = f"lambda_{rate}"
        results[rate_key] = []

        for days in elapsed_days_grid:
            graph = EpistemicConceptGraph(review_threshold=0.50)
            graph.add_node("prereq_01", "Prerequisite Concept", domain="Math", decay_rate=rate)
            graph.add_node("target_01", "Target Concept", domain="Math", prerequisites=["prereq_01"])

            for m0 in initial_mastery_levels:
                t0 = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
                graph.nodes["prereq_01"].update_mastery(new_mastery=m0, timestamp=t0)
                
                curr_m = graph.nodes["prereq_01"].current_mastery()
                diag = graph.check_diagnostic_review("target_01")
                dist = graph.compute_concept_distance("target_01")

                results[rate_key].append({
                    "elapsed_days": days,
                    "initial_mastery": m0,
                    "retained_mastery": round(curr_m, 4),
                    "concept_distance": round(dist, 4),
                    "review_triggered": diag["needs_review"]
                })

    return results

if __name__ == "__main__":
    res = run_experiment_5()
    print("--- Experiment 5 Results (Epistemic Decay) ---")
    for rate_key, rows in res.items():
        print(f"\nDecay Rate: {rate_key}")
        for r in rows[:6]:
            print(f"Days: {r['elapsed_days']:2} | Initial: {r['initial_mastery']} -> Retained: {r['retained_mastery']} | Review Triggered: {r['review_triggered']}")
