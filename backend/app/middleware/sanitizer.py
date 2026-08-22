"""
MAES LLM Guardrails & Input Sanitization Suite
Enforces:
  1. Prompt injection & Jailbreak defense
  2. Pedagogical integrity & anti-bypass guardrails
  3. XSS and script stripping
  4. Structured XML envelope protection for LLMs
"""
import re
from typing import Tuple

# Patterns that attempt to hijack LLM behavior or leak internal instructions
JAILBREAK_PATTERNS = [
    r"\bignore\s+(all\s+)?(previous|prior|above)\s+instructions?\b",
    r"\bdisregard\s+(all\s+)?(previous|prior)\s+rules?\b",
    r"\byou\s+are\s+now\s+in\s+dan\s+mode\b",
    r"\breveal\s+(your\s+)?(system\s+prompt|initial\s+instructions?)\b",
    r"\bprint\s+(your\s+)?system\s+prompt\b",
    r"\boutput\s+(your\s+)?hidden\s+prompt\b",
    r"\bpretend\s+you\s+have\s+no\s+(rules|restrictions|guidelines)\b",
    r"\bforget\s+that\s+you\s+are\s+a\s+(tutor|teacher|auditor)\b",
    r"\bdo\s+anything\s+now\b"
]

# Patterns that attempt to short-circuit the Socratic dialogue
BYPASS_PATTERNS = [
    r"\bjust\s+give\s+me\s+the\s+(answer|solution|code|final\s+result)\b",
    r"\bdon'?t\s+ask\s+me\s+questions,\s+just\s+(tell|solve)\b",
    r"\bskip\s+the\s+(socratic|questions|tutoring|hints)\b",
    r"\bstop\s+asking\s+questions\s+and\s+give\s+me\s+the\s+answer\b"
]

def sanitize_student_input(text: str) -> str:
    """
    Sanitizes user input to prevent prompt injection and XSS.
    Strips HTML tags, controls length, and cleans control characters.
    """
    if not text:
        return ""
    
    # 1. Truncate extreme lengths
    text = text[:3000]
    
    # 2. Strip HTML and XML tags to prevent markup injection
    clean_text = re.sub(r'<[^>]+>', '', text)
    
    # 3. Strip null bytes and non-printable control chars (except newline/tab)
    clean_text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', clean_text)
    
    return clean_text.strip()

def check_guardrails(text: str) -> Tuple[bool, str]:
    """
    Evaluates student text against security and pedagogical guardrail rules.
    Returns: (is_safe: bool, warning_message: str)
    """
    lower = text.lower()
    
    # Check for adversarial jailbreak attempts
    for pattern in JAILBREAK_PATTERNS:
        if re.search(pattern, lower):
            return False, "Your message triggered an administrative prompt guardrail. Please focus your inquiry on the subject material."
            
    # Check for explicit Socratic bypass attempts
    for pattern in BYPASS_PATTERNS:
        if re.search(pattern, lower):
            return True, "[GUARDRAIL_SIGNAL: STUDENT_REQUESTING_BYPASS]"
            
    return True, ""

def wrap_for_llm(sanitized_text: str, student_profile: dict = None) -> str:
    """
    Wraps student input in XML delimiters so the LLM treats it strictly as data.
    Optionally injects personalization metadata.
    """
    profile_meta = ""
    if student_profile:
        pref = student_profile.get("preferred_style", "socratic")
        mastery = student_profile.get("mastery_level", "intermediate")
        profile_meta = f'\n  <student_profile preferred_style="{pref}" mastery="{mastery}" />'

    return f"<student_turn>{profile_meta}\n  <content>\n    {sanitized_text}\n  </content>\n</student_turn>"
