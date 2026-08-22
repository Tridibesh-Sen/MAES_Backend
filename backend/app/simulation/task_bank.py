"""
Benchmark Task Bank & STEM Curriculum DAG (IEEE TLT Specification - Section D)
Defines structured multi-concept curriculum graphs and tasks across Mathematics & Computer Science.
"""
from app.core.epistemic_graph import EpistemicConceptGraph

def build_math_concept_graph() -> EpistemicConceptGraph:
    """Builds a Calculus curriculum graph with prerequisite chains."""
    graph = EpistemicConceptGraph(review_threshold=0.50)
    
    # 1. Foundation: Algebra & Limits
    graph.add_node("alg_01", "Algebraic Factoring", domain="Mathematics", decay_rate=0.03)
    graph.add_node("lim_01", "Limit Definition & Continuity", domain="Mathematics", prerequisites=["alg_01"], decay_rate=0.04)
    
    # 2. Differential Calculus
    graph.add_node("der_01", "Derivative Definition (Difference Quotient)", domain="Mathematics", prerequisites=["lim_01"], decay_rate=0.05)
    graph.add_node("der_02", "Power & Product Rules", domain="Mathematics", prerequisites=["der_01"], decay_rate=0.04)
    graph.add_node("der_03", "Chain Rule", domain="Mathematics", prerequisites=["der_02"], decay_rate=0.06)
    
    # 3. Advanced Applications
    graph.add_node("app_01", "Optimization & Related Rates", domain="Mathematics", prerequisites=["der_03"], decay_rate=0.07)
    
    return graph

def build_cs_concept_graph() -> EpistemicConceptGraph:
    """Builds a Computer Science (Data Structures & Algorithms) curriculum graph."""
    graph = EpistemicConceptGraph(review_threshold=0.50)
    
    # 1. Foundation
    graph.add_node("cs_arr", "Array Memory Layout & Indexing", domain="Computer Science", decay_rate=0.02)
    graph.add_node("cs_rec", "Recursion & Stack Frames", domain="Computer Science", prerequisites=["cs_arr"], decay_rate=0.05)
    
    # 2. Divide & Conquer
    graph.add_node("cs_bin", "Binary Search", domain="Computer Science", prerequisites=["cs_arr"], decay_rate=0.04)
    graph.add_node("cs_tree", "Binary Search Trees (BST)", domain="Computer Science", prerequisites=["cs_rec", "cs_bin"], decay_rate=0.06)
    graph.add_node("cs_dijk", "Graph Traversal & Shortest Path", domain="Computer Science", prerequisites=["cs_tree"], decay_rate=0.07)
    
    return graph

BENCHMARK_TASKS = [
    {
        "task_id": "math_chain_rule_01",
        "domain": "Mathematics",
        "concept_id": "der_03",
        "title": "Derivative of Composite Functions (Chain Rule)",
        "prompt": "Find the derivative of f(x) = (3x^2 + 5x)^4 with respect to x.",
        "difficulty": 0.55,
        "solution_essence": "Apply outer derivative 4*(3x^2+5x)^3 multiplied by inner derivative (6x+5)",
        "common_misconception": "Omitting the inner derivative (6x+5) and only differentiating the outer power."
    },
    {
        "task_id": "math_limits_01",
        "domain": "Mathematics",
        "concept_id": "lim_01",
        "title": "Indeterminate Form Limits",
        "prompt": "Evaluate the limit as x approaches 2 of (x^2 - 4) / (x - 2).",
        "difficulty": 0.40,
        "solution_essence": "Factor numerator into (x-2)(x+2), cancel the removable discontinuity, and evaluate at x=2 to get 4.",
        "common_misconception": "Claiming limit is undefined because denominator evaluates to 0 directly."
    },
    {
        "task_id": "cs_bst_traversal_01",
        "domain": "Computer Science",
        "concept_id": "cs_tree",
        "title": "In-Order BST Traversal Property",
        "prompt": "Explain why in-order traversal on a Binary Search Tree always outputs elements in sorted ascending order.",
        "difficulty": 0.60,
        "solution_essence": "Because in-order recursively visits left subtree (all smaller), then root, then right subtree (all larger).",
        "common_misconception": "Confusing in-order with pre-order or level-order traversal."
    }
]
