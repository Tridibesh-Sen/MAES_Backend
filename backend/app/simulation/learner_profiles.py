"""
Simulated Learner Persona Benchmark (IEEE TLT Specification - Section D)
Defines 7 mathematically parameterizable simulated learner personas with exact
stochastic distributions for correctness probability, response latency, hesitation markers,
and misconception manifestation.
"""
import random
from typing import Dict, Any, Optional

class SimulatedLearner:
    def __init__(
        self,
        profile_name: str,
        base_mastery: float,
        alpha_beta: tuple[float, float], # Beta distribution parameters (a, b)
        latency_mean_sd: tuple[float, float], # Normal distribution (mean_sec, sd_sec)
        hesitation_prob: float,
        misconception_prob: float,
        learning_rate: float, # Delta mastery per received scaffold
        description: str
    ):
        self.profile_name = profile_name
        self.base_mastery = base_mastery
        self.current_mastery = base_mastery
        self.alpha, self.beta = alpha_beta
        self.latency_mean, self.latency_sd = latency_mean_sd
        self.hesitation_prob = hesitation_prob
        self.misconception_prob = misconception_prob
        self.learning_rate = learning_rate
        self.description = description
        self.turn_count = 0

    def generate_turn_behavior(
        self,
        hint_received: Optional[str] = None,
        register_received: Optional[str] = None,
        task_difficulty: float = 0.50
    ) -> Dict[str, Any]:
        """
        Simulates the learner's response turn given the tutor's prior hint and current state.
        Returns behavioral telemetry (latency, backspaces, pause count, correctness, text).
        """
        self.turn_count += 1

        # 1. Update mastery if tutor provided scaffold
        if hint_received and register_received:
            scaffold_multiplier = {
                "socratic": 1.0,
                "analogy_first": 1.3,
                "worked_example": 1.6,
                "error_correction": 1.8
            }.get(register_received, 1.0)
            self.current_mastery = min(1.0, self.current_mastery + (self.learning_rate * scaffold_multiplier))

        # 2. Probability of correct deduction
        effective_p = max(0.05, min(0.95, self.current_mastery - (task_difficulty * 0.25)))
        is_correct = random.random() < effective_p

        # 3. Misconception trigger
        has_misconception = (not is_correct) and (random.random() < self.misconception_prob)

        # 4. Latency sampling N(mean, sd) clamped >= 1.0s
        raw_latency = random.gauss(self.latency_mean, self.latency_sd)
        latency = max(1.0, raw_latency)

        # 5. Hesitation & Backspaces
        hesitates = random.random() < self.hesitation_prob
        if hesitates:
            backspaces = random.randint(3, 12)
            pauses = random.randint(1, 4)
            prefix_hedge = random.choice(["I think maybe ", "I'm not completely sure, but ", "Perhaps ", "Um, is it "])
        else:
            backspaces = random.randint(0, 2)
            pauses = 0
            prefix_hedge = ""

        # 6. Response Message Synthesis
        if is_correct:
            response_text = f"{prefix_hedge}the key insight is following the standard derivative definition."
        elif has_misconception:
            response_text = f"{prefix_hedge}I thought we could simply distribute the power or cancel out the denominator directly."
        else:
            response_text = f"{prefix_hedge}I am getting stuck on how to apply the step here."

        return {
            "profile_name": self.profile_name,
            "turn": self.turn_count,
            "current_mastery": round(self.current_mastery, 4),
            "is_correct": is_correct,
            "has_misconception": has_misconception,
            "latency_seconds": round(latency, 2),
            "backspace_count": backspaces,
            "pause_count": pauses,
            "student_message": response_text
        }


def get_all_learner_profiles() -> Dict[str, SimulatedLearner]:
    """Returns factory instances of all 7 benchmark learner profiles."""
    return {
        "high_mastery_low_hesitation": SimulatedLearner(
            profile_name="high_mastery_low_hesitation",
            base_mastery=0.85,
            alpha_beta=(8.0, 2.0),
            latency_mean_sd=(4.0, 1.0),
            hesitation_prob=0.05,
            misconception_prob=0.05,
            learning_rate=0.08,
            description="High domain competence, rapid execution, minimal hesitations."
        ),
        "medium_mastery": SimulatedLearner(
            profile_name="medium_mastery",
            base_mastery=0.50,
            alpha_beta=(5.0, 5.0),
            latency_mean_sd=(9.0, 2.0),
            hesitation_prob=0.25,
            misconception_prob=0.20,
            learning_rate=0.10,
            description="Average competence, moderate hesitation, steady progression."
        ),
        "low_mastery_high_hesitation": SimulatedLearner(
            profile_name="low_mastery_high_hesitation",
            base_mastery=0.20,
            alpha_beta=(2.0, 8.0),
            latency_mean_sd=(18.0, 4.0),
            hesitation_prob=0.65,
            misconception_prob=0.45,
            learning_rate=0.06,
            description="Low initial competence, prolonged latencies, frequent corrections."
        ),
        "misconception_prone": SimulatedLearner(
            profile_name="misconception_prone",
            base_mastery=0.35,
            alpha_beta=(4.0, 6.0),
            latency_mean_sd=(7.0, 2.0),
            hesitation_prob=0.15,
            misconception_prob=0.70,
            learning_rate=0.09,
            description="Confident but systematic erroneous conceptual priors."
        ),
        "forgotten_prerequisite": SimulatedLearner(
            profile_name="forgotten_prerequisite",
            base_mastery=0.60,
            alpha_beta=(6.0, 4.0),
            latency_mean_sd=(14.0, 3.5),
            hesitation_prob=0.50,
            misconception_prob=0.30,
            learning_rate=0.05,
            description="Competent in target surface syntax but blocked by degraded prerequisite memory."
        ),
        "rapid_recovery": SimulatedLearner(
            profile_name="rapid_recovery",
            base_mastery=0.30,
            alpha_beta=(3.0, 7.0),
            latency_mean_sd=(11.0, 2.5),
            hesitation_prob=0.40,
            misconception_prob=0.20,
            learning_rate=0.22,
            description="Low initial state but high cognitive responsiveness to Socratic hints."
        ),
        "persistent_struggle": SimulatedLearner(
            profile_name="persistent_struggle",
            base_mastery=0.15,
            alpha_beta=(1.5, 8.5),
            latency_mean_sd=(22.0, 5.0),
            hesitation_prob=0.75,
            misconception_prob=0.50,
            learning_rate=0.03,
            description="Requires multi-turn PID controller escalation to break conceptual impasse."
        ),
    }
