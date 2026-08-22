from openai import AsyncOpenAI
from app.config import settings
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Agent S, the Fallback Socratic Tutor.
You are only invoked when the primary agents are experiencing errors.
Your goal is to guide the student to the answer without ever giving it to them directly.
Keep your responses concise, encouraging, and supportive.
"""

def get_agent_s_client() -> AsyncOpenAI:
    """Initializes and returns Agent S (Fallback) client using Mistral AI."""
    api_key = settings.mistral_agent_s_key or settings.mistral_api_key
    return AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.mistral.ai/v1"
    )

async def fallback_hint(student_message: str, sources_text: str = "") -> str:
    """Generates a fallback hint directly using Mistral AI."""
    try:
        from app.main import increment_agent_call
        increment_agent_call("agent_s")
    except Exception:
        pass

    try:
        client = get_agent_s_client()
        context = f"Sources:\n{sources_text[:5000]}\n\n" if sources_text else ""
        prompt = f"{context}Student: {student_message}"
        
        response = await client.chat.completions.create(
            model=settings.fallback_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Fallback Agent S failed: {e}")
        return "That is an intriguing question. What is the fundamental concept or relationship that comes to mind first?"
