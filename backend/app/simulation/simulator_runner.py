"""
Closed-Loop Simulation Episode Runner (IEEE TLT Specification - Section C & E)
Executes multi-turn tutoring episodes between simulated learner profiles and
system architectures (Direct LLM, Single-Agent Socratic, Dual-Agent Open-Loop, Full MAES).
Logs all 14 state variables per turn.
"""
import time
import logging
from typing import Dict, Any, List, Optional
from app.core.scaffold_controller import PIDScaffoldController
from app.core.psi_engine import PSIEngine
from app.core.epistemic_graph import EpistemicConceptGraph
from app.simulation.learner_profiles import SimulatedLearner

logger = logging.getLogger(__name__)

class SimulationEpisodeRunner:
    def __init__(
        self,
        system_type: str = "full_maes", # "direct_llm" | "single_socratic" | "dual_open_loop" | "full_maes"
        target_psi: float = 0.40,
        concept_graph: Optional[EpistemicConceptGraph] = None
    ):
        self.system_type = system_type
        self.controller = PIDScaffoldController(target_psi=target_psi)
        self.psi_engine = PSIEngine()
        self.concept_graph = concept_graph

    def run_episode(
        self,
        learner: SimulatedLearner,
        task: Dict[str, Any],
        max_turns: int = 8
    ) -> Dict[str, Any]:
        """
        Runs a complete closed-loop tutoring episode of up to max_turns.
        """
        self.controller.reset()
        episode_logs = []
        hint = None
        register = "socratic"
        concept_id = task.get("concept_id", "concept_generic")
        leakage_detected = False

        for turn_k in range(1, max_turns + 1):
            t_start = time.perf_counter()

            # 1. Simulated Learner produces response & chronometrics
            learner_output = learner.generate_turn_behavior(
                hint_received=hint,
                register_received=register,
                task_difficulty=task.get("difficulty", 0.5)
            )

            # 2. Compute Concept Distance from Epistemic Graph
            concept_dist = 0.0
            if self.concept_graph and concept_id in self.concept_graph.nodes:
                concept_dist = self.concept_graph.compute_concept_distance(concept_id)

            # 3. Compute Composite PSI
            psi_res = self.psi_engine.compute_psi(
                latency_seconds=learner_output["latency_seconds"],
                backspace_count=learner_output["backspace_count"],
                pause_count=learner_output["pause_count"],
                student_message=learner_output["student_message"],
                concept_distance=concept_dist
            )
            observed_psi = psi_res["psi"]

            # 4. Controller Stepping (depending on system condition)
            if self.system_type == "full_maes":
                u, register, ctrl_telemetry = self.controller.compute_step(observed_psi)
            elif self.system_type == "dual_open_loop":
                # Fixed threshold without PID integral/derivative adaptation
                u = 0.25 if observed_psi < 0.50 else 0.75
                register = self.controller.map_register(u)
                ctrl_telemetry = {"error": observed_psi - 0.40, "u_clamped": u, "register": register}
            elif self.system_type == "single_socratic":
                # Fixed Socratic register always
                u = 0.15
                register = "socratic"
                ctrl_telemetry = {"error": observed_psi - 0.40, "u_clamped": u, "register": register}
            else: # direct_llm
                # Direct didactic output
                u = 1.00
                register = "direct_answer"
                ctrl_telemetry = {"error": observed_psi - 0.40, "u_clamped": u, "register": register}

            # 5. Scaffold / Hint Generation (Simulated or Real Model)
            hint, turn_leakage = self._generate_hint_for_register(register, task, turn_k)
            if turn_leakage:
                leakage_detected = True

            # 6. Auditor Decision (in dual / full MAES)
            auditor_decision = "APPROVE"
            if self.system_type in ["full_maes", "dual_open_loop"]:
                # If direct LLM leaks or hint violates rubric, request revision
                if turn_leakage and self.system_type == "full_maes":
                    auditor_decision = "REQUEST_REVISION"
                    # Correct hint to eliminate leakage
                    hint = f"Consider how the definition of {task['title']} applies here without jumping to the final formula."
                    turn_leakage = False

            t_end = time.perf_counter()
            processing_latency = round((t_end - t_start) * 1000, 2) # ms

            # 7. Complete 14-Variable Turn Log Record
            turn_record = {
                "turn_number": turn_k,
                "learner_profile": learner.profile_name,
                "task_id": task.get("task_id"),
                "student_message": learner_output["student_message"],
                "latency_variable": learner_output["latency_seconds"],
                "hesitation_markers": learner_output["backspace_count"] + learner_output["pause_count"],
                "concept_distance": round(concept_dist, 4),
                "observed_psi": observed_psi,
                "pid_error": round(ctrl_telemetry.get("error", 0.0), 4),
                "control_output_u": round(u, 4),
                "active_register": register,
                "generated_hint": hint,
                "auditor_decision": auditor_decision,
                "revisions_count": 1 if auditor_decision == "REQUEST_REVISION" else 0,
                "leakage_occurred": turn_leakage,
                "learner_mastery_post": learner_output["current_mastery"],
                "processing_latency_ms": processing_latency
            }
            episode_logs.append(turn_record)

            # Exit early if learner achieved full mastery
            if learner_output["current_mastery"] >= 0.90 and turn_k >= 3:
                break

        return {
            "system_type": self.system_type,
            "learner_profile": learner.profile_name,
            "task_id": task.get("task_id"),
            "total_turns": len(episode_logs),
            "final_mastery": episode_logs[-1]["learner_mastery_post"] if episode_logs else 0.0,
            "leakage_in_episode": leakage_detected,
            "mean_tracking_error": round(sum(abs(r["pid_error"]) for r in episode_logs) / len(episode_logs), 4),
            "turns_data": episode_logs
        }

    def _generate_hint_for_register(self, register: str, task: Dict[str, Any], turn: int) -> tuple[str, bool]:
        """Generates representative scaffold text and checks for answer leakage."""
        if register == "direct_answer":
            return f"The complete solution is: {task['solution_essence']}", True
        elif register == "error_correction":
            return f"Notice that {task.get('common_misconception', 'this approach')} is a common pitfall. Let's correct that specific part.", False
        elif register == "worked_example":
            return f"Here is a similar structured step: First identify the outer function, then compute its derivative.", False
        elif register == "analogy_first":
            return f"Think of this like peeling an onion: you differentiate from the outside layer first, then the inner core.", False
        else: # Socratic
            return f"What happens to the rate of change when we look at the composition of these two functions?", False
