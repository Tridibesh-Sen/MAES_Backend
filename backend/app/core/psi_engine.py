"""
Pedagogical Struggle Index (PSI) Engine (IEEE TLT Specification - Section F)
Computes multi-factor composite PSI from behavioral chronometrics, lexical hesitation,
and epistemic concept distance:
  PSI[k] = alpha * L_norm[k] + beta * H_norm[k] + gamma * D_concept[k]
"""
import re
from typing import Dict, Any, List

HESITATION_LEXICON = [
    r"\bi think\b", r"\bmaybe\b", r"\bnot sure\b", r"\bperhaps\b",
    r"\bum\b", r"\buh\b", r"\bprobably\b", r"\bi guess\b",
    r"\bi don't know\b", r"\bconfused\b", r"\bi forget\b", r"\bis it\b"
]

class PSIEngine:
    def __init__(
        self,
        alpha: float = 0.40,      # Weight for latency
        beta: float = 0.35,       # Weight for hesitation / corrections
        gamma: float = 0.25,      # Weight for concept distance / prerequisite gap
        max_expected_latency: float = 30.0, # Max expected turn think+typing time in seconds
    ):
        assert abs((alpha + beta + gamma) - 1.0) < 1e-4, "Weights alpha, beta, gamma must sum to 1.0"
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.max_expected_latency = max_expected_latency

    def compute_psi(
        self,
        latency_seconds: float,
        backspace_count: int,
        pause_count: int,
        student_message: str,
        concept_distance: float = 0.0
    ) -> Dict[str, Any]:
        """
        Calculates the normalized PSI value for a student turn.
        
        Args:
            latency_seconds: Total time taken to respond (seconds).
            backspace_count: Number of backspace/delete events during drafting.
            pause_count: Number of cursor pauses > 2 seconds.
            student_message: Raw text of student response.
            concept_distance: Normalized graph distance to prerequisite mastery [0.0, 1.0].
            
        Returns:
            Dict containing normalized components and final composite PSI score.
        """
        # 1. Normalized Latency L_norm in [0, 1]
        l_norm = min(1.0, max(0.0, latency_seconds / self.max_expected_latency))

        # 2. Normalized Hesitation H_norm in [0, 1]
        # Lexical marker detection
        msg_lower = student_message.lower()
        lexical_hedges = sum(1 for pattern in HESITATION_LEXICON if re.search(pattern, msg_lower))
        
        # Combined hesitation score: backspaces + long pauses + lexical hedges
        raw_hesitation = (backspace_count * 0.10) + (pause_count * 0.25) + (lexical_hedges * 0.30)
        h_norm = min(1.0, max(0.0, raw_hesitation))

        # 3. Concept Distance D_concept in [0, 1]
        d_norm = min(1.0, max(0.0, concept_distance))

        # 4. Composite PSI Equation
        psi = (self.alpha * l_norm) + (self.beta * h_norm) + (self.gamma * d_norm)
        psi = max(0.0, min(1.0, psi))

        # Categorize struggle zone
        zone = self.categorize_struggle(psi)

        return {
            "psi": round(psi, 4),
            "zone": zone,
            "components": {
                "l_norm": round(l_norm, 4),
                "h_norm": round(h_norm, 4),
                "d_norm": round(d_norm, 4),
            },
            "weights": {
                "alpha": self.alpha,
                "beta": self.beta,
                "gamma": self.gamma
            },
            "raw_inputs": {
                "latency_seconds": latency_seconds,
                "backspace_count": backspace_count,
                "pause_count": pause_count,
                "lexical_hedges": lexical_hedges,
                "concept_distance": concept_distance
            }
        }

    @staticmethod
    def categorize_struggle(psi: float) -> str:
        """Categorizes PSI into educational struggle zones."""
        if psi < 0.25:
            return "low_struggle"         # High fluency / recall
        elif psi <= 0.60:
            return "productive_struggle"  # Optimal ZPD (Zone of Proximal Development)
        else:
            return "excessive_struggle"   # Cognitive overload / conceptual impasse
