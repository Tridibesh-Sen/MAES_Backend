from openai import AsyncOpenAI
from groq import AsyncGroq
from app.config import settings
import json
import logging
from app.services.json_utils import repair_and_parse_json

logger = logging.getLogger(__name__)

AGENT_A_SYSTEM = """
You are Agent A: the AI Teacher in an adaptive pedagogical tutoring system.
Your goal is to scaffold student learning according to the specified `current_register`:

PEDAGOGICAL REGISTERS:
1. 'socratic': Pure Socratic inquiry. Ask probing, thought-provoking questions that guide the student to discover the answer themselves. Do NOT give away the direct answer or algebraic steps.
2. 'analogy_first': Frame the concept using an intuitive real-world or physical analogy first, then guide the student to apply it to the problem.
3. 'worked_example': Provide a structured, step-by-step parallel example or sub-step to model the reasoning process.
4. 'error_correction': Directly address and explain the specific misconception or error the student made, providing targeted remediation.

CRITICAL INSTRUCTION: If the user explicitly asks you to generate a quiz, questions, a summary, or any other content, you MUST generate that content fully and completely within your `hint_text`. 
DO NOT use conversational filler like "I will generate it". Output the actual generated content immediately.
Speak naturally and warmly as a great teacher. NEVER echo or output XML/HTML tags like `<student_turn>` or `<content>` in your response.

Always respond with a JSON object only:
{
  "hint_text": "... (Keep your response concise, max 3-4 short paragraphs, strictly formatted in the current_register)",
  "internal_reasoning": "...",
  "estimated_bloom_level": "remember|understand|apply|analyze|evaluate|create"
}
"""

async def run_agent_a(state: dict) -> dict:
    try:
        from app.main import increment_agent_call
        increment_agent_call("agent_a")
    except Exception:
        pass

    correction = state.get("agent_b_signal", {})
    correction_note = ""
    if correction and correction.get("correction"):
        correction_note = f"\n\nAUDIT CORRECTION: {correction['correction']}"
    if correction and correction.get("register_switch"):
        correction_note += f"\nSWITCH REGISTER TO: {correction['register_switch']}"

    history_str = ""
    history_list = state.get("dialogue_history", [])
    if history_list:
        history_str = "\n\nDIALOGUE HISTORY:\n" + "\n".join([
            f"{'Student' if h['role'] == 'student' else 'Tutor'}: {h['text']}" for h in history_list
        ])

    payload = {
        "student_message": state["student_message"],
        "dialogue_history": state.get("dialogue_history", []),
        "learner_model": state.get("learner_model", {}),
        "current_register": state.get("current_register", "socratic")
    }

    # Inject cognitive state context into user payload
    cognitive_context = {}
    if state.get("active_misconception"):
        cognitive_context["active_misconception"] = state["active_misconception"]
    if state.get("chronometric_load_score", 0) > 0:
        cognitive_context["chronometric_load_score"] = state["chronometric_load_score"]
    if state.get("bloom_stall_count", 0) > 0:
        cognitive_context["bloom_stall_count"] = state["bloom_stall_count"]
    if cognitive_context:
        payload["cognitive_context"] = cognitive_context

    prompt_text = f"RESPOND TO THIS STATE:\n{json.dumps(payload, indent=2)}\n\n"
    if state.get("active_sources"):
        prompt_text += f"\n--- PROVIDED DOCUMENTS/SOURCES ---\n{state['active_sources']}\n-----------------------------------\n"
        prompt_text += "\nCRITICAL: You MUST read the PROVIDED DOCUMENTS/SOURCES above to answer the user. Do NOT claim you don't have access to the document, the full text is provided right above this line."
    
    if correction_note:
        prompt_text += correction_note

    messages = [
        {"role": "system", "content": AGENT_A_SYSTEM},
        {"role": "user", "content": prompt_text}
    ]

    draft = None
    mistral_key = settings.mistral_agent_a_key or settings.mistral_api_key
    groq_key = settings.groq_agent_b_key or settings.groq_api_key

    used_model = None
    agent_status = "online"

    # 1. Primary: Mistral AI (try configured model, then accessible fallbacks)
    if mistral_key:
        mistral_models = [settings.agent_a_model, "codestral-latest", "ministral-8b-latest"]
        mistral_models = list(dict.fromkeys([m for m in mistral_models if m]))
        client = AsyncOpenAI(api_key=mistral_key, base_url="https://api.mistral.ai/v1")
        
        for model_name in mistral_models:
            try:
                response = await client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.7,
                    max_tokens=1500
                )
                draft = repair_and_parse_json(response.choices[0].message.content)
                if draft and draft.get("hint_text"):
                    used_model = model_name
                    agent_status = "online"
                    break
            except Exception as e:
                logger.warning(f"Agent A Mistral call ({model_name}) failed: {e}")

    # 2. Secondary: Groq Fallback
    if not draft or not draft.get("hint_text"):
        if groq_key:
            groq_models = [settings.agent_b_model, "qwen/qwen3.8-27b", "openai/gpt-oss-120b", "llama-3.3-70b-versatile"]
            groq_models = list(dict.fromkeys([m for m in groq_models if m]))
            groq_client = AsyncGroq(api_key=groq_key)
            
            for g_model in groq_models:
                try:
                    response = await groq_client.chat.completions.create(
                        model=g_model,
                        messages=messages,
                        response_format={"type": "json_object"},
                        temperature=0.7,
                        max_tokens=1500
                    )
                    draft = repair_and_parse_json(response.choices[0].message.content)
                    if draft and draft.get("hint_text"):
                        used_model = f"Groq {g_model}"
                        agent_status = "fallback"
                        break
                except Exception as e2:
                    logger.warning(f"Agent A Groq fallback ({g_model}) failed: {e2}")

    # 3. Tertiary: In-memory dynamic scaffolding if all external APIs are unreachable
    if not draft or not draft.get("hint_text"):
        logger.warning("Agent A all LLM providers failed. Using in-memory scaffolding.")
        used_model = "In-Memory Scaffolding"
        agent_status = "fallback"
        reg = state.get("current_register", "socratic")
        msg = state.get("student_message", "")
        if reg == "analogy_first":
            hint_txt = f"Let's think about this conceptually: how would you relate \"{msg}\" to an everyday physical process before diving into calculations?"
        elif reg == "worked_example":
            hint_txt = f"Let's break this down into clear logical steps. Step 1: Identify your givens and the core relationship at play. What is the first principle you can apply here?"
        elif reg == "error_correction":
            hint_txt = f"Let's review the core definition relevant to \"{msg}\". Notice where the standard formula differs from the current assumption."
        else:
            hint_txt = f"That's a thoughtful question on \"{msg}\". What fundamental rule or relationship connecting these terms comes to mind first?"

        draft = {
            "hint_text": hint_txt,
            "internal_reasoning": f"Generated under {reg} register.",
            "estimated_bloom_level": "understand"
        }

    try:
        from app.main import record_agent_execution
        record_agent_execution("agent_a", agent_status, used_model or settings.agent_a_model)
    except Exception:
        pass
    
    # Log to Neon
    try:
        from app.db.neon_client import log_event
        is_revision = "AUDIT CORRECTION" in correction_note
        log_text = "Agent A: Drafted revised response based on Agent B feedback." if is_revision else "Agent A: Drafted initial response based on active register."
        await log_event(
            session_id=state.get("session_id", ""),
            student_id=state.get("student_id", ""),
            event_type="agent_a",
            text=log_text,
            status="agent"
        )
    except Exception:
        pass
    
    return {**state, "agent_a_draft": draft}
