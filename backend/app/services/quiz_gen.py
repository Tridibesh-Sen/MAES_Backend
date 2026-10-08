import logging
from groq import AsyncGroq
from openai import AsyncOpenAI
from app.config import settings
from app.services.json_utils import repair_and_parse_json
from app.db.neon_client import log_event

logger = logging.getLogger(__name__)

async def generate_quiz(
    context: str, 
    num_questions: int = 5, 
    difficulty: str = "medium", 
    learner_model: dict = None, 
    history: list = None,
    session_id: str = "",
    student_id: str = ""
) -> list[dict]:
    """Generates a multiple choice quiz adapted to user's Bloom levels and working concepts using Groq LLaMA 3.3 70B with Mistral fallback."""
    profile_instructions = ""
    if learner_model:
        bloom_history = learner_model.get('bloom_level_history', ['understand'])
        profile_instructions += f"\n- Target Bloom Level: {bloom_history[-1] if bloom_history else 'understand'}"
        profile_instructions += f"\n- Mastered Concepts: {learner_model.get('mastered_concepts', [])}"
        profile_instructions += f"\n- Working Concepts: {learner_model.get('working_concepts', [])}"
        profile_instructions += f"\n- Preferred Pedagogical Style: {learner_model.get('preferred_style', 'socratic')}"
        
    if history:
        recent_topics = [h.get("content", "") for h in history if h.get("role") == "student"][-5:]
        if recent_topics:
            profile_instructions += f"\n- Student Recent Discussion Areas: {', '.join(recent_topics)}"
            
    personalization_prompt = ""
    if profile_instructions:
        personalization_prompt = f"""PERSONALIZATION ADAPTATION METRICS:
{profile_instructions}

Tailor questions to address these working concepts and align difficulty with the student's cognitive state."""

    prompt = f"""You are an expert educator. Create a {difficulty} difficulty, {num_questions}-question multiple-choice quiz based on the provided text.
Ensure questions test conceptual understanding and application.

{personalization_prompt}

Source Text:
{context[:15000] if context else "General principles of science and engineering."}

Respond STRICTLY in the following JSON format containing a list under the key "questions", and nothing else:
{{
  "questions": [
    {{
      "question": "Question text...",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_index": 0,
      "explanation": "Why this answer is correct...",
      "bloom_level": "understand"
    }}
  ]
}}"""

    await log_event(
        session_id=session_id or "studio-generation",
        student_id=student_id or "student",
        event_type="studio_quiz_start",
        text=f"Studio: Generating {num_questions} {difficulty}-difficulty quiz questions adapted to student Bloom level.",
        status="running"
    )

    try:
        # Primary: Groq LLaMA 3.3 70B
        client = AsyncGroq(api_key=settings.groq_agent_b_key or settings.groq_api_key)
        model_to_use = settings.agent_b_model or "qwen/qwen3.8-27b"
        response = await client.chat.completions.create(
            model=model_to_use,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=950,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        quiz = repair_and_parse_json(content)
        result = _normalize_quiz(quiz)
        
        await log_event(
            session_id=session_id or "studio-generation",
            student_id=student_id or "student",
            event_type="studio_quiz_done",
            text=f"Studio: Successfully created {len(result)} adaptive quiz questions via Groq LLaMA 3.3 70B.",
            status="done"
        )
        return result
    except Exception as e:
        logger.warning(f"Groq quiz generation failed ({e}). Attempting Mistral fallback.")
        try:
            mistral_client = AsyncOpenAI(api_key=settings.mistral_agent_a_key or settings.mistral_api_key, base_url="https://api.mistral.ai/v1")
            response = await mistral_client.chat.completions.create(
                model=settings.agent_a_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            quiz = repair_and_parse_json(content)
            result = _normalize_quiz(quiz)
            
            await log_event(
                session_id=session_id or "studio-generation",
                student_id=student_id or "student",
                event_type="studio_quiz_fallback",
                text=f"Studio: Generated {len(result)} adaptive quiz questions via Mistral Large fallback.",
                status="done"
            )
            return result
        except Exception as e2:
            logger.error(f"Quiz generation failed on all models: {e2}")
            return [
                {
                    "question": "What is the primary goal of the uploaded study materials?",
                    "options": ["Understand core principles", "Memorize without context", "Skip foundational theory", "Ignore practical applications"],
                    "correct_index": 0,
                    "explanation": "Understanding foundational concepts enables application to complex problems.",
                    "bloom_level": "understand"
                }
            ]

def _normalize_quiz(quiz) -> list[dict]:
    if isinstance(quiz, list):
        return quiz
    elif isinstance(quiz, dict):
        for key in ["questions", "quiz", "data"]:
            if key in quiz and isinstance(quiz[key], list):
                return quiz[key]
        return [quiz]
    return []
