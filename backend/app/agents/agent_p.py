"""
Agent P: Peer Epistemic Conflict Generator
Blueprint: Build epistemic conflict generator based on misconception seeds.
LLM: Mistral Large (deviation: blueprint recommended Gemini, user approved Mistral for agents)
"""
import json
from openai import AsyncOpenAI
from app.config import settings
from app.services.json_utils import repair_and_parse_json

AGENT_P_SYSTEM = """
You are Agent P: the Peer Epistemic Conflict Agent. Your role is to create a productive intellectual challenge for the student by surfacing the tension between what they currently believe and the correct concept.

Rules:
- Do NOT reveal the correct answer directly.
- Frame your challenge as a Socratic counter-question or a thought experiment.
- Reference the student's specific misconception to make the challenge feel personal and targeted.
- Your challenge should make the student pause and reconsider, not feel attacked.

Always respond with a JSON object only:
{
  "hint_text": "...",
  "peer_challenge": true,
  "targeted_misconception": "...",
  "internal_reasoning": "..."
}
"""

async def run_agent_p(state: dict) -> dict:
    """
    Generates a Socratic counter-question to challenge the student's active misconception.
    Called when Agent B decides PEER_REQUIRED (bloom_stall_count >= 3).
    """
    try:
        from app.main import increment_agent_call
        increment_agent_call("agent_p")
    except Exception:
        pass

    active_misconception = state.get("active_misconception") or "general conceptual misunderstanding"
    
    payload = {
        "student_message": state["student_message"],
        "active_misconception": active_misconception,
        "dialogue_history": state.get("dialogue_history", [])[-6:],  # last 6 turns for context
        "current_register": state.get("current_register", "socratic"),
        "bloom_stall_count": state.get("bloom_stall_count", 0),
        "learner_model": state.get("learner_model", {})
    }

    messages = [
        {"role": "system", "content": AGENT_P_SYSTEM},
        {"role": "user", "content": f"Generate a peer epistemic challenge for this state:\n{json.dumps(payload, indent=2)}"}
    ]

    try:
        client = AsyncOpenAI(api_key=settings.mistral_agent_p_key, base_url="https://api.mistral.ai/v1")
        response = await client.chat.completions.create(
            model=settings.agent_p_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.6,
            max_tokens=2000
        )
        result = repair_and_parse_json(response.choices[0].message.content)
    except Exception as e:
        result = {
            "hint_text": "Consider this perspective: could there be a fundamental constraint we overlooked?",
            "peer_challenge": True,
            "targeted_misconception": active_misconception,
            "internal_reasoning": f"Fallback peer challenge: {e}"
        }
    
    # Log to Neon
    from app.db.neon_client import log_event
    await log_event(
        session_id=state.get("session_id", ""),
        student_id=state.get("student_id", ""),
        event_type="agent_p",
        text=f"Agent P: Formulated Misconception-Targeted Epistemic Conflict (MTECG) to address '{active_misconception[:50]}'.",
        status="agent"
    )
    
    # Store in agent_a_draft format so Agent B can evaluate it uniformly
    peer_draft = {
        "hint_text": result.get("hint_text", ""),
        "internal_reasoning": result.get("internal_reasoning", ""),
        "estimated_bloom_level": "analyze",  # Peer challenges are inherently analytical
        "peer_challenge": True,
        "targeted_misconception": result.get("targeted_misconception", active_misconception)
    }
    
    return {**state, "agent_a_draft": peer_draft, "peer_challenge": True}
