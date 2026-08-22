"""
DVS Generator (Component 6): Dynamic Visual Scaffolding
Blueprint: Generate SVG visuals when students stall. Render inline in chat.
LLM: Groq Llama 3.3-70B (fallback from Gemini due to quota limits)
"""
import re
import logging
from groq import AsyncGroq
from app.config import settings

logger = logging.getLogger(__name__)

DVS_SYSTEM_PROMPT = """You are a visual educator. Generate a self-contained inline SVG diagram that visually explains the concept the student is stuck on.

STRICT SVG RULES:
- Use viewBox="0 0 800 500" and width="800" height="500"
- All content must be inline — no external references, no <image> tags with URLs
- Use clear text labels, arrows (marker defs), and colored rectangles/circles
- Suitable diagrams: concept maps, data structure visualizations, flowcharts, timelines, algorithm steps
- Use these colors: background #0F172A, text #E2E8F0, boxes #1E3A5F, accent #10B981, arrows #4F46E5
- Font: use font-family="monospace" for labels

CRITICAL: Respond with ONLY the raw SVG markup starting with <svg and ending with </svg>. No explanation, no markdown code fences, no other text.
"""

async def run_dvs_generator(state: dict) -> dict:
    """
    Generates an inline SVG visual scaffold when Agent B decides DVS_REQUIRED.
    Triggered when student's chronometric_load_score > 0.7 (cognitively overloaded).
    """
    try:
        from app.main import increment_agent_call
        increment_agent_call("dvs")
    except Exception:
        pass

    student_message = state.get("student_message", "")
    active_misconception = state.get("active_misconception") or "the concept the student is asking about"
    active_sources = state.get("active_sources", "")

    context_snippet = ""
    if active_sources:
        context_snippet = f"\nRELEVANT SOURCE CONTEXT:\n{active_sources[:2000]}"

    user_prompt = f"""The student asked: "{student_message}"
Their known misconception: {active_misconception}
{context_snippet}

Generate an SVG diagram that visually explains the core concept they are struggling with. Make it clear, labeled, and educational. Output ONLY the raw SVG, starting with <svg."""

    try:
        client = AsyncGroq(api_key=settings.groq_dvs_key)
        response = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": DVS_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )

        raw = response.choices[0].message.content.strip()

        # Extract SVG block robustly
        svg_match = re.search(r'<svg[\s\S]*?</svg>', raw, re.IGNORECASE)
        svg_payload = svg_match.group(0) if svg_match else None

        if not svg_payload:
            logger.warning("[DVS] LLM did not return a valid SVG block.")
            return {**state, "dvs_payload": None}

        # Log the DVS event to Neon
        try:
            from app.db.neon_client import get_neon_pool, log_event
            pool = get_neon_pool()
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO dvs_events (session_id, trigger_reason, svg_payload)
                    VALUES ($1, $2, $3)
                """,
                    state.get("session_id", ""),
                    f"CLS:{state.get('chronometric_load_score', 0.0):.2f} | misconception: {active_misconception[:80]}",
                    svg_payload
                )
            
            await log_event(
                session_id=state.get("session_id", ""),
                student_id=state.get("student_id", ""),
                event_type="dvs",
                text="DVS: Generating Dynamic Visual Scaffolding diagram to shift learning modality.",
                status="success"
            )
        except Exception as e:
            logger.error(f"[DVS] Failed to log dvs_event to Neon: {e}")

        logger.info(f"[DVS] SVG generated successfully ({len(svg_payload)} chars)")
        return {**state, "dvs_payload": svg_payload}

    except Exception as e:
        logger.error(f"[DVS] Generation failed: {e}")
        return {**state, "dvs_payload": None}
