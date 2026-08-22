import logging
from typing import Optional
from supabase import create_client, Client
from app.config import settings

logger = logging.getLogger(__name__)

def _init_supabase() -> Optional[Client]:
    if settings.supabase_url and settings.supabase_service_role_key:
        try:
            return create_client(settings.supabase_url, settings.supabase_service_role_key)
        except Exception as e:
            logger.warning(f"Supabase client initialization failed ({e}). Running in offline/memory mode.")
            return None
    return None

supabase: Optional[Client] = _init_supabase()

def get_supabase() -> Optional[Client]:
    """Returns the primary Supabase client."""
    return supabase

def get_learner_model(student_id: str) -> dict:
    if not supabase:
        return {}
    try:
        response = supabase.table("learner_models").select("*").eq("student_id", student_id).execute()
        if response.data:
            return response.data[0]
    except Exception as e:
        logger.warning(f"Learner models table missing or error: {e}")
    return {}

def update_learner_model(student_id: str, updates: dict):
    if not supabase:
        return
    try:
        supabase.table("learner_models").upsert({"student_id": student_id, **updates}).execute()
    except Exception:
        pass

def create_session(session_id: str, student_id: str, domain: str, notebook_id: str = None):
    if not supabase:
        return
    data = {
        "id": session_id,
        "student_id": student_id,
        "domain": domain,
        "is_active": True
    }
    if notebook_id:
        data["notebook_id"] = notebook_id
    try:
        supabase.table("sessions").insert(data).execute()
    except Exception as e:
        logger.warning(f"Failed to create session in Supabase: {e}")

def end_session(session_id: str):
    if not supabase:
        return
    import datetime
    try:
        supabase.table("sessions").update({
            "is_active": False,
            "ended_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }).eq("id", session_id).execute()
    except Exception:
        pass

def save_message(session_id: str, role: str, content: str):
    if not supabase:
        return
    try:
        supabase.table("messages").insert({
            "session_id": session_id,
            "role": role,
            "content": content
        }).execute()
    except Exception as e:
        logger.warning(f"Failed to save message to Supabase: {e}")

def get_student_history(student_id: str) -> list:
    if not supabase:
        return []
    try:
        sessions_res = supabase.table("sessions").select("id").eq("student_id", student_id).execute()
        if not sessions_res.data:
            return []
        session_ids = [s["id"] for s in sessions_res.data]
        
        messages_res = supabase.table("messages").select("role, content, created_at")\
            .in_("session_id", session_ids)\
            .order("created_at", desc=False)\
            .execute()
            
        history = [{"role": m["role"], "text": m["content"]} for m in messages_res.data]
        return history
    except Exception as e:
        logger.warning(f"Failed to fetch student history: {e}")
        return []
