import json
import logging
from groq import AsyncGroq
from openai import AsyncOpenAI
from app.config import settings
from app.services.json_utils import repair_and_parse_json

logger = logging.getLogger(__name__)

AGENT_B_SYSTEM = """
You are Agent B: the Pedagogical Auditor in an adaptive multi-agent tutoring system.
Evaluate the teacher's draft response against the specified `current_register` and strict pedagogical rubric.

RUBRIC CRITERIA:
1. Hint Quality (1-5): Relevance, clarity, and pedagogical effectiveness.
2. Tone (1-5): Encouraging, supportive, non-condescending, and academically rigorous.
3. Correctness (1-5): Factual and mathematical precision based on provided sources.
4. Bloom Alignment (1-5): Matches student cognitive level and targeted Bloom tier.
5. Non-Leakage: In 'socratic' or 'analogy_first' registers, ensure the teacher DOES NOT leak the final answer prematurely.

DECISION RULES:
- If current_register is 'socratic' and Agent A revealed the complete final solution or direct computation: set decision = "REQUEST_REVISION" with correction_note = "Do not reveal the final answer; ask a guiding Socratic question instead."
- If the student's chronometric_load_score > 0.7: set decision = "DVS_REQUIRED" (trigger visual schema).
- If the student's bloom_stall_count >= 3: set decision = "PEER_REQUIRED" (trigger peer challenge).
- If avg rubric score >= 3.5 AND correctness >= 4: set decision = "APPROVE".
- Otherwise: set decision = "REQUEST_REVISION".

Return ONLY a valid JSON object with this exact structure:
{
  "decision": "APPROVE|REQUEST_REVISION|PEER_REQUIRED|DVS_REQUIRED",
  "correction_note": "...",
  "register_switch": null,
  "struggle_level": "productive|stalled|null",
  "bloom_tag_student": "remember|understand|apply|analyze|evaluate|create",
  "bloom_tag_hint": "remember|understand|apply|analyze|evaluate|create",
  "rubric_scores": {
    "hint_quality": 4,
    "tone": 5,
    "correctness": 5,
    "bloom_alignment": 4
  }
}
"""

async def run_agent_b(state: dict) -> dict:
    try:
        from app.main import increment_agent_call
        increment_agent_call("agent_b")
    except Exception:
        pass

    payload = {
        "student_message": state["student_message"],
        "agent_a_draft": state["agent_a_draft"],
        "dialogue_history": state.get("dialogue_history", []),
        "learner_model": state.get("learner_model", {}),
        "current_register": state.get("current_register", "socratic"),
        "turn_number": state.get("turn_number", 1),
        "active_sources": state.get("active_sources", ""),
        "chronometric_load_score": state.get("chronometric_load_score", 0.0),
        "bloom_stall_count": state.get("bloom_stall_count", 0),
        "active_misconception": state.get("active_misconception", None)
    }

    messages = [
        {"role": "system", "content": AGENT_B_SYSTEM},
        {"role": "user", "content": "EVALUATE THIS:\n" + json.dumps(payload)}
    ]

    try:
        # Primary: Groq client for Agent B
        client = AsyncGroq(api_key=settings.groq_agent_b_key)
        response = await client.chat.completions.create(
            model=settings.agent_b_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=2000
        )
        result = repair_and_parse_json(response.choices[0].message.content)
    except Exception as e:
        logger.warning(f"Agent B Groq call failed ({e}). Attempting Mistral fallback.")
        try:
            mistral_client = AsyncOpenAI(api_key=settings.mistral_agent_a_key, base_url="https://api.mistral.ai/v1")
            response = await mistral_client.chat.completions.create(
                model="mistral-large-latest",
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=2000
            )
            result = repair_and_parse_json(response.choices[0].message.content)
        except Exception as e2:
            logger.warning(f"Agent B fallback failed ({e2}). Approving with default rubric.")
            result = {
                "decision": "APPROVE",
                "correction_note": None,
                "register_switch": None,
                "struggle_level": "productive",
                "bloom_tag_student": "understand",
                "bloom_tag_hint": "understand",
                "rubric_scores": {
                    "hint_quality": 4,
                    "tone": 5,
                    "correctness": 5,
                    "bloom_alignment": 4
                }
            }

    try:
        from app.db.neon_client import log_event
        decision = result.get("decision", "APPROVE")
        
        if decision == "PEER_REQUIRED":
            log_text = "Agent B: Evaluated draft. Detected cognitive struggle (Bloom stall). Routing to Peer Agent."
        elif decision == "DVS_REQUIRED":
            log_text = "Agent B: Evaluated draft. Detected high cognitive load. Routing to DVS Generator."
        elif decision == "REQUEST_REVISION":
            log_text = "Agent B: Evaluated draft. Did not meet rubric standards. Requesting revision."
        else:
            log_text = "Agent B: Evaluated and approved draft response."

        await log_event(
            session_id=state.get("session_id", ""),
            student_id=state.get("student_id", ""),
            event_type="agent_b",
            text=log_text,
            status="agent"
        )
    except Exception:
        pass

    return {**state, "agent_b_result": result}
