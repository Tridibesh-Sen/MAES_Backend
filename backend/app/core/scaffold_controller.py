"""
Discrete-Time PID Scaffold Controller (IEEE TLT Specification - Section G)
Regulates scaffold intensity u[k] in closed-loop tutoring based on observed PSI.
Maps continuous control output u[k] in [0.0, 1.0] to discrete pedagogical registers:
  [0.00, 0.25) -> Socratic (pure inquiry, minimal direct assistance)
  [0.25, 0.50) -> Analogy-First (conceptual bridge)
  [0.50, 0.75) -> Worked Example (structural step-by-step scaffold)
  [0.75, 1.00] -> Error Correction / Didactic (direct remediation)
"""
from typing import Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)

class PIDScaffoldController:
    def __init__(
        self,
        target_psi: float = 0.40,      # Target zone of productive struggle (ZPD)
        kp: float = 0.85,             # Proportional gain
        ki: float = 0.20,             # Integral gain
        kd: float = 0.15,             # Derivative gain
        dt: float = 1.0,              # Discrete turn step
        integral_max: float = 0.50,   # Anti-windup clamping threshold
        filter_alpha: float = 0.30,   # Derivative low-pass filter coefficient
    ):
        self.target_psi = target_psi
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.dt = dt
        self.integral_max = integral_max
        self.filter_alpha = filter_alpha

        # Internal state
        self.prev_error = 0.0
        self.integral = 0.0
        self.filtered_derivative = 0.0
        self.turn_count = 0
        self.history: list[Dict[str, Any]] = []

    def reset(self):
        """Resets controller state for a new tutoring session."""
        self.prev_error = 0.0
        self.integral = 0.0
        self.filtered_derivative = 0.0
        self.turn_count = 0
        self.history = []

    def compute_step(self, observed_psi: float) -> Tuple[float, str, Dict[str, float]]:
        """
        Executes one discrete PID update turn.
        
        Args:
            observed_psi: Normalized Pedagogical Struggle Index in [0.0, 1.0]
            
        Returns:
            Tuple of:
              - u[k]: Continuous control output clamped to [0.0, 1.0]
              - register: Active pedagogical register string
              - telemetry: Dict containing P, I, D terms, error, and raw signal
        """
        # 1. Error calculation: positive error means student struggle > target
        error = observed_psi - self.target_psi

        # 2. Proportional term
        p_term = self.kp * error

        # 3. Integral term with Anti-Windup clamping
        self.integral += error * self.dt
        self.integral = max(-self.integral_max, min(self.integral_max, self.integral))
        i_term = self.ki * self.integral

        # 4. Derivative term with first-order low-pass noise filter
        raw_derivative = (error - self.prev_error) / self.dt if self.turn_count > 0 else 0.0
        self.filtered_derivative = (
            self.filter_alpha * raw_derivative + (1.0 - self.filter_alpha) * self.filtered_derivative
        )
        d_term = self.kd * self.filtered_derivative

        # 5. Raw Control Signal
        # Baseline scaffold bias is 0.25 (default Socratic baseline)
        raw_u = 0.25 + p_term + i_term + d_term

        # 6. Bound to [0.0, 1.0]
        u = max(0.0, min(1.0, raw_u))

        # 7. Map to Pedagogical Register
        register = self.map_register(u)

        # 8. Telemetry tracking
        telemetry = {
            "turn": self.turn_count + 1,
            "target_psi": self.target_psi,
            "observed_psi": observed_psi,
            "error": error,
            "p_term": p_term,
            "i_term": i_term,
            "d_term": d_term,
            "u_raw": raw_u,
            "u_clamped": u,
            "register": register
        }
        self.history.append(telemetry)

        # Update previous state
        self.prev_error = error
        self.turn_count += 1

        return u, register, telemetry

    @staticmethod
    def map_register(u: float) -> str:
        """Maps continuous control output u in [0, 1] to discrete pedagogical registers."""
        if u < 0.25:
            return "socratic"
        elif u < 0.50:
            return "analogy_first"
        elif u < 0.75:
            return "worked_example"
        else:
            return "error_correction"

    def is_stable(self, window: int = 4, tolerance: float = 0.10) -> bool:
        """
        Operational stability criterion:
        Trajectory is stable if tracking error variance and absolute error stay within tolerance.
        """
        if len(self.history) < window:
            return False
        recent_errors = [h["error"] for h in self.history[-window:]]
        mean_abs_error = sum(abs(e) for e in recent_errors) / window
        variance = sum((e - (sum(recent_errors) / window)) ** 2 for e in recent_errors) / window
        return mean_abs_error <= tolerance and variance <= (tolerance ** 2)
