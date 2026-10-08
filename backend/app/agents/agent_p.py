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

    result = None
    mistral_key = settings.mistral_agent_p_key or settings.mistral_api_key
    groq_key = settings.groq_agent_b_key or settings.groq_api_key

    used_model = None
    agent_status = "online"

    # 1. Primary: Mistral
    if mistral_key:
        mistral_models = [settings.agent_p_model, "codestral-latest", "ministral-8b-latest"]
        mistral_models = list(dict.fromkeys([m for m in mistral_models if m]))
        client = AsyncOpenAI(api_key=mistral_key, base_url="https://api.mistral.ai/v1")
        
        for m_model in mistral_models:
            try:
                response = await client.chat.completions.create(
                    model=m_model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.6,
                    max_tokens=2000
                )
                result = repair_and_parse_json(response.choices[0].message.content)
                if result and result.get("hint_text"):
                    used_model = m_model
                    agent_status = "online"
                    break
            except Exception:
                pass

    # 2. Secondary: Groq Fallback
    if not result or not result.get("hint_text"):
        if groq_key:
            from groq import AsyncGroq
            groq_models = [settings.agent_b_model, "qwen/qwen3.8-27b", "openai/gpt-oss-120b"]
            groq_models = list(dict.fromkeys([m for m in groq_models if m]))
            groq_client = AsyncGroq(api_key=groq_key)
            for g_model in groq_models:
                try:
                    response = await groq_client.chat.completions.create(
                        model=g_model,
                        messages=messages,
                        response_format={"type": "json_object"},
                        temperature=0.6,
                        max_tokens=2000
                    )
                    result = repair_and_parse_json(response.choices[0].message.content)
                    if result and result.get("hint_text"):
                        used_model = f"Groq {g_model}"
                        agent_status = "fallback"
                        break
                except Exception:
                    pass

    if not result or not result.get("hint_text"):
        used_model = "Rule-based Peer Prompt"
        agent_status = "fallback"
        result = {
            "hint_text": "Consider this perspective: could there be a fundamental constraint we overlooked?",
            "peer_challenge": True,
            "targeted_misconception": active_misconception,
            "internal_reasoning": "Fallback peer challenge triggered."
        }

    try:
        from app.main import record_agent_execution
        record_agent_execution("agent_p", agent_status, used_model or settings.agent_p_model)
    except Exception:
        pass
    
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
