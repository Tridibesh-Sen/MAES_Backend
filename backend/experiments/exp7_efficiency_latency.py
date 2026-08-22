"""
Experiment 7: Computational Efficiency & Latency Profiling (IEEE TLT Specification - Section E)
Measures end-to-end turn latency, audit latency, LangGraph revision rates, token usage,
and approximate operational cost per 1,000 turns.
"""
from typing import Dict, Any, List
from app.simulation.learner_profiles import get_all_learner_profiles
from app.simulation.task_bank import build_math_concept_graph, BENCHMARK_TASKS
from app.simulation.simulator_runner import SimulationEpisodeRunner

# Pricing assumptions ($ / 1M tokens) - Groq Llama 3.1 8B ($0.05/M) & Mistral Large ($2.00/M)
COST_PER_TEACHER_TURN = 0.00008 # ~$0.08 per 1k turns
COST_PER_AUDIT_TURN = 0.00150   # ~$1.50 per 1k turns

def run_experiment_7(episodes_per_condition: int = 10) -> Dict[str, Any]:
    systems = ["single_socratic", "dual_open_loop", "full_maes"]
    graph = build_math_concept_graph()
    results = {}

    for sys_type in systems:
        runner = SimulationEpisodeRunner(system_type=sys_type, concept_graph=graph)
        latencies = []
        revision_counts = []
        total_turns = 0

        for _ in range(episodes_per_condition):
            profiles = get_all_learner_profiles()
            for prof_name, learner in profiles.items():
                for task in BENCHMARK_TASKS:
                    ep_res = runner.run_episode(learner, task, max_turns=6)
                    for t in ep_res["turns_data"]:
                        total_turns += 1
                        latencies.append(t["processing_latency_ms"])
                        revision_counts.append(t["revisions_count"])

        mean_lat = sum(latencies) / len(latencies) if latencies else 0.0
        sorted_lat = sorted(latencies)
        p95_lat = sorted_lat[int(len(sorted_lat) * 0.95)] if sorted_lat else 0.0
        rev_rate = (sum(revision_counts) / total_turns) * 100.0 if total_turns else 0.0

        # Cost estimation per 1k turns
        if sys_type == "single_socratic":
            cost_per_1k = COST_PER_TEACHER_TURN * 1000
        else:
            cost_per_1k = (COST_PER_TEACHER_TURN + COST_PER_AUDIT_TURN + (rev_rate/100.0 * COST_PER_TEACHER_TURN)) * 1000

        results[sys_type] = {
            "total_turns": total_turns,
            "mean_latency_ms": round(mean_lat, 2),
            "p95_latency_ms": round(p95_lat, 2),
            "revision_trigger_rate_pct": round(rev_rate, 2),
            "estimated_cost_per_1k_turns_usd": round(cost_per_1k, 4)
        }

    return results

if __name__ == "__main__":
    res = run_experiment_7(episodes_per_condition=3)
    print("--- Experiment 7 Results (Computational Efficiency) ---")
    for k, v in res.items():
        print(f"System: {k:20} | Mean Latency: {v['mean_latency_ms']} ms | P95: {v['p95_latency_ms']} ms | Cost/1k: ${v['estimated_cost_per_1k_turns_usd']}")
