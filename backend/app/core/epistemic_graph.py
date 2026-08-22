"""
Epistemic Concept Graph & Memory Decay Module (IEEE TLT Specification - Section C & E)
Models curriculum prerequisite relationships as a Directed Acyclic Graph (DAG),
tracks mastery per concept node, models Ebbinghaus-style exponential decay,
and computes prerequisite diagnostic-review triggers and concept distances.
"""
import math
import datetime
from typing import Dict, List, Optional, Any

class ConceptNode:
    def __init__(
        self,
        node_id: str,
        name: str,
        domain: str,
        prerequisites: Optional[List[str]] = None,
        decay_rate: float = 0.05, # Lambda per day
    ):
        self.node_id = node_id
        self.name = name
        self.domain = domain
        self.prerequisites: List[str] = prerequisites or []
        self.decay_rate = decay_rate
        self.initial_mastery: float = 0.0
        self.last_practiced: datetime.datetime = datetime.datetime.now(datetime.timezone.utc)

    def current_mastery(self, as_of: Optional[datetime.datetime] = None) -> float:
        """Calculates decayed mastery M(t) = M_0 * exp(-lambda * delta_t_days)."""
        now = as_of or datetime.datetime.now(datetime.timezone.utc)
        elapsed_days = max(0.0, (now - self.last_practiced).total_seconds() / 86400.0)
        decayed = self.initial_mastery * math.exp(-self.decay_rate * elapsed_days)
        return max(0.0, min(1.0, decayed))

    def update_mastery(self, new_mastery: float, timestamp: Optional[datetime.datetime] = None):
        """Updates node mastery and resets practice timestamp."""
        self.initial_mastery = max(0.0, min(1.0, new_mastery))
        self.last_practiced = timestamp or datetime.datetime.now(datetime.timezone.utc)


class EpistemicConceptGraph:
    def __init__(self, review_threshold: float = 0.50):
        self.nodes: Dict[str, ConceptNode] = {}
        self.review_threshold = review_threshold

    def add_node(
        self,
        node_id: str,
        name: str,
        domain: str,
        prerequisites: Optional[List[str]] = None,
        decay_rate: float = 0.05
    ) -> ConceptNode:
        node = ConceptNode(node_id, name, domain, prerequisites, decay_rate)
        self.nodes[node_id] = node
        return node

    def get_prerequisite_chain(self, node_id: str) -> List[str]:
        """Recursively traverses all prerequisite ancestor nodes."""
        if node_id not in self.nodes:
            return []
        visited = set()
        stack = [node_id]
        chain = []
        while stack:
            curr = stack.pop()
            if curr not in self.nodes or curr in visited:
                continue
            visited.add(curr)
            if curr != node_id:
                chain.append(curr)
            for prereq in self.nodes[curr].prerequisites:
                if prereq not in visited:
                    stack.append(prereq)
        return chain

    def compute_concept_distance(self, target_node_id: str, as_of: Optional[datetime.datetime] = None) -> float:
        """
        Computes normalized concept distance D_concept in [0.0, 1.0].
        Calculated as the average mastery gap across all prerequisite ancestors of the target concept.
        """
        prereqs = self.get_prerequisite_chain(target_node_id)
        if not prereqs:
            return 0.0
        
        gaps = []
        for pid in prereqs:
            if pid in self.nodes:
                mastery = self.nodes[pid].current_mastery(as_of)
                gaps.append(max(0.0, 1.0 - mastery))
        
        return sum(gaps) / len(gaps) if gaps else 0.0

    def check_diagnostic_review(
        self,
        target_node_id: str,
        as_of: Optional[datetime.datetime] = None
    ) -> Tuple_Diagnostic:
        """
        Evaluates whether any prerequisite node has decayed below the review threshold.
        Returns: (needs_review, weakest_prereq_id, weakest_prereq_mastery)
        """
        prereqs = self.get_prerequisite_chain(target_node_id)
        weakest_id = None
        lowest_mastery = 1.0

        for pid in prereqs:
            if pid in self.nodes:
                m = self.nodes[pid].current_mastery(as_of)
                if m < lowest_mastery:
                    lowest_mastery = m
                    weakest_id = pid

        needs_review = lowest_mastery < self.review_threshold and weakest_id is not None
        return {
            "needs_review": needs_review,
            "weakest_prereq_id": weakest_id,
            "prereq_name": self.nodes[weakest_id].name if weakest_id else None,
            "weakest_mastery": round(lowest_mastery, 4),
            "threshold": self.review_threshold
        }


# Type alias for diagnostic return
Tuple_Diagnostic = Dict[str, Any]
