import logging
from groq import AsyncGroq
from openai import AsyncOpenAI
from app.config import settings
from app.services.json_utils import repair_and_parse_json
from app.db.neon_client import log_event

logger = logging.getLogger(__name__)

async def generate_flashcards(context: str, topic: str = None, history: list = None, session_id: str = "", student_id: str = "") -> list[dict]:
    """Generates flashcards from source context and chat history using Groq LLaMA 3.3 70B with Mistral fallback."""
    topic_str = f"Focus specifically on the topic: {topic}" if topic else "Cover the main concepts comprehensively."
    
    history_context = ""
    if history:
        recent_topics = [h.get("content", "") for h in history if h.get("role") == "student"][-5:]
        if recent_topics:
            history_context = f"\nRecent student chat discussion topics to draw inspiration from: {', '.join(recent_topics)}"
    
    prompt = f"""You are an expert educator. Extract key facts, definitions, and concepts from the provided text and chat history, and convert them into high-quality educational flashcards.
{topic_str}
{history_context}

Source Text:
{context[:15000] if context else "General knowledge and fundamental principles."}

Respond STRICTLY in the following JSON format inside a JSON object with key "flashcards", and nothing else:
{{
  "flashcards": [
    {{"front": "Question or concept...", "back": "Answer or definition..."}}
  ]
}}
Generate between 5 and 10 flashcards."""

    await log_event(
        session_id=session_id or "studio-generation",
        student_id=student_id or "student",
        event_type="studio_flashcards_start",
        text=f"Studio: Initiating flashcard generation for topic: '{topic or 'General'}' using Groq LLaMA 3.3 70B.",
        status="running"
    )

    try:
        # Primary: Groq LLaMA 3.3 70B
        client = AsyncGroq(api_key=settings.groq_agent_b_key or settings.groq_api_key)
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        cards = repair_and_parse_json(content)
        result = _normalize_cards(cards)
        
        await log_event(
            session_id=session_id or "studio-generation",
            student_id=student_id or "student",
            event_type="studio_flashcards_done",
            text=f"Studio: Successfully generated {len(result)} flashcards via Groq LLaMA 3.3 70B.",
            status="done"
        )
        return result
    except Exception as e:
        logger.warning(f"Groq flashcard generation failed ({e}). Attempting Mistral fallback.")
        try:
            mistral_client = AsyncOpenAI(api_key=settings.mistral_agent_a_key or settings.mistral_api_key, base_url="https://api.mistral.ai/v1")
            response = await mistral_client.chat.completions.create(
                model=settings.agent_a_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1500,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            cards = repair_and_parse_json(content)
            result = _normalize_cards(cards)
            
            await log_event(
                session_id=session_id or "studio-generation",
                student_id=student_id or "student",
                event_type="studio_flashcards_fallback",
                text=f"Studio: Generated {len(result)} flashcards via Mistral Large fallback.",
                status="done"
            )
            return result
        except Exception as e2:
            logger.error(f"Flashcard generation failed on all models: {e2}")
            # Resilient fallback cards
            return [
                {"front": "Core Principle", "back": f"Review key concepts related to {topic or 'the uploaded sources'}."},
                {"front": "Key Term", "back": "Fundamental definition from your study materials."}
            ]

def _normalize_cards(cards) -> list[dict]:
    if isinstance(cards, list):
        return cards
    elif isinstance(cards, dict):
        for key in ["flashcards", "cards", "data"]:
            if key in cards and isinstance(cards[key], list):
                return cards[key]
        return [cards]
    return []
