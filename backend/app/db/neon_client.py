import asyncpg
import json
import logging
import re
from app.config import settings

logger = logging.getLogger(__name__)

_pool = None

async def init_neon_pool():
    global _pool
    if not _pool and settings.neon_database_url:
        try:
            # Clean up URL for asyncpg
            dsn = settings.neon_database_url
            # Strip channel_binding if present as asyncpg handles TLS internally
            dsn = re.sub(r'[?&]channel_binding=[^&]*', '', dsn)
            if '?' in dsn and dsn.endswith('?'):
                dsn = dsn[:-1]

            _pool = await asyncpg.create_pool(
                dsn, 
                min_size=1, 
                max_size=10,
                command_timeout=10,
                timeout=5
            )
            logger.info("Neon database connection pool initialized successfully.")

            # Auto-create telemetry tables on Neon
            async with _pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS audit_logs (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        session_id VARCHAR(255),
                        student_id VARCHAR(255),
                        event_type VARCHAR(100),
                        text TEXT,
                        status VARCHAR(50),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );

                    CREATE TABLE IF NOT EXISTS pedagogy_metrics (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        session_id VARCHAR(255),
                        student_id VARCHAR(255),
                        turn_number INT,
                        cls_score FLOAT,
                        bloom_stall_count INT,
                        active_misconception TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                logger.info("Neon telemetry tables verified/created successfully.")
        except Exception as e:
            logger.warning(f"Neon database pool initialization failed ({e}). Proceeding in offline/development mode.")
            _pool = None

async def close_neon_pool():
    global _pool
    if _pool:
        try:
            await _pool.close()
        except Exception as e:
            logger.warning(f"Error closing Neon pool: {e}")
        _pool = None
        logger.info("Neon database connection pool closed.")

def get_neon_pool():
    """Returns the Neon pool if available, otherwise None."""
    return _pool

async def log_audit_entry(session_id: str, student_id: str, turn_number: int, data: dict):
    """Logs an agent turn audit event to the Neon database."""
    pool = get_neon_pool()
    if not pool:
        return
        
    try:
        metadata = {
            "turn_number": turn_number,
            "student_message": data.get("student_message"),
            "hint_delivered": data.get("hint_delivered"),
            "bloom_tag_student": data.get("bloom_tag_student"),
            "bloom_tag_hint": data.get("bloom_tag_hint"),
            "register_at_turn": data.get("register_at_turn"),
            "decision": data.get("decision"),
            "correction_applied": data.get("correction_applied", False),
            "struggle_level": data.get("struggle_level"),
            "scores": {
                "hint_quality": data.get("score_hint_quality"),
                "tone": data.get("score_tone"),
                "correctness": data.get("score_correctness"),
                "bloom_alignment": data.get("score_bloom_alignment")
            }
        }
        
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO audit_logs (session_id, student_id, event_type, text, status)
                VALUES ($1, $2, $3, $4, $5)
            """,
                session_id,
                student_id,
                "audit",
                json.dumps(metadata),
                data.get("decision", "APPROVED")
            )
    except Exception as e:
        logger.warning(f"Failed to log audit entry to Neon: {e}")

async def log_event(session_id: str, student_id: str, event_type: str, text: str, status: str = "info"):
    """Generic logger for system telemetry events to Neon and memory buffer."""
    try:
        from app.routes.audit import record_memory_log
        record_memory_log(session_id, event_type, text, status)
    except Exception:
        pass

    pool = get_neon_pool()
    if not pool:
        return
        
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO audit_logs (session_id, student_id, event_type, text, status)
                VALUES ($1, $2, $3, $4, $5)
            """,
                session_id,
                student_id,
                event_type,
                text,
                status
            )
    except Exception as e:
        logger.warning(f"Failed to log event to Neon: {e}")
