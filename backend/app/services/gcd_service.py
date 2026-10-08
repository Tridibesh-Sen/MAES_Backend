"""
GCD Service (Component 7): Generalized Conceptual Difficulty tracking
Blueprint: detect misconceptions, log to gcd_profiles, feed Agent P.
LLM: Groq Llama 3.3-70B (fallback from Gemini due to quota limits)
"""
import logging
import json
from groq import AsyncGroq
from app.config import settings

logger = logging.getLogger(__name__)

GCD_CLASSIFY_PROMPT = """You are a pedagogical misconception detector. Analyze the student's message and determine if it reveals a clear conceptual misconception.

A misconception is a specific wrong belief about how something works (not just a mistake or uncertainty).

Respond with JSON only:
{
  "has_misconception": true|false,
  "concept": "name of the concept involved",
  "misconception_text": "brief description of what the student believes incorrectly (null if none)"
}"""


async def detect_and_log_misconception(
    session_id: str,
    student_id: str,
    student_message: str,
    bloom_tag: str
) -> None:
    """
    Uses Groq to classify if the student message reveals a conceptual misconception.
    If detected, logs to gcd_profiles in Neon DB.
    Called as a BackgroundTask after each turn.
    """
    try:
        groq_key = settings.groq_api_key or settings.groq_agent_b_key
        if not groq_key:
            return
        client = AsyncGroq(api_key=groq_key)
        response = await client.chat.completions.create(
            model=settings.agent_b_model,
            messages=[
                {"role": "system", "content": GCD_CLASSIFY_PROMPT},
                {"role": "user", "content": f"Student message: \"{student_message}\"\nBloom level detected: {bloom_tag}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=200
        )

        from app.services.json_utils import repair_and_parse_json
        result = repair_and_parse_json(response.choices[0].message.content)

        if result.get("has_misconception") and result.get("misconception_text"):
            # Log to Neon gcd_profiles
            try:
                from app.db.neon_client import get_neon_pool
                pool = get_neon_pool()
                async with pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO gcd_profiles (student_id, session_id, concept, misconception_text)
                        VALUES ($1, $2, $3, $4)
                    """,
                        student_id,
                        session_id,
                        result.get("concept", "unknown"),
                        result["misconception_text"]
                    )
                logger.info(f"[GCD] Misconception logged: {result['misconception_text'][:60]}")
            except Exception as e:
                logger.error(f"[GCD] Failed to log misconception to Neon: {e}")

    except Exception as e:
        logger.error(f"[GCD] Groq classification failed: {e}")


async def get_active_misconception(student_id: str) -> str | None:
    """
    Fetches the latest unresolved misconception for a student to seed Agent P.
    Returns the misconception_text or None if no unresolved misconceptions exist.
    """
    try:
        from app.db.neon_client import get_neon_pool
        pool = get_neon_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT misconception_text FROM gcd_profiles
                WHERE student_id = $1 AND resolved_at IS NULL
                ORDER BY detected_at DESC
                LIMIT 1
            """, student_id)

        if row:
            return row["misconception_text"]
        return None

    except Exception as e:
        logger.error(f"[GCD] Failed to fetch active misconception: {e}")
        return None


async def resolve_misconception(student_id: str, concept: str) -> None:
    """
    Marks a misconception as resolved once Agent P's challenge is answered correctly.
    """
    try:
        from app.db.neon_client import get_neon_pool
        pool = get_neon_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE gcd_profiles
                SET resolved_at = now()
                WHERE student_id = $1 AND concept = $2 AND resolved_at IS NULL
            """, student_id, concept)
    except Exception as e:
        logger.error(f"[GCD] Failed to resolve misconception: {e}")
