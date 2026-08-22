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

    try:
        # Mistral client for Agent A
        client = AsyncOpenAI(api_key=settings.mistral_agent_a_key, base_url="https://api.mistral.ai/v1")
        response = await client.chat.completions.create(
            model=settings.agent_a_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=1500
        )
        draft = repair_and_parse_json(response.choices[0].message.content)
    except Exception as e:
        logger.warning(f"Agent A Mistral call failed ({e}). Attempting Groq fallback.")
        try:
            groq_client = AsyncGroq(api_key=settings.groq_agent_b_key)
            response = await groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=1500
            )
            draft = repair_and_parse_json(response.choices[0].message.content)
        except Exception as e2:
            logger.warning(f"Agent A fallback failed ({e2}). Using in-memory scaffolding.")
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
