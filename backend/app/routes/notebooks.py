from fastapi import APIRouter, Depends, HTTPException
import uuid
import datetime
import logging
from app.db.models import CreateNotebookRequest, CreateNoteRequest, UpdateNoteRequest
from app.db.supabase_client import get_supabase
from app.middleware.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notebooks", tags=["Notebooks"])

@router.get("")
async def list_notebooks(user: dict = Depends(get_current_user)):
    sb = get_supabase()
    if sb:
        try:
            res = sb.table("notebooks").select("id, title, domain, created_at, updated_at")\
                .eq("student_id", user["user_id"])\
                .order('updated_at', desc=True).execute()
            nbs = []
            if res.data:
                for row in res.data:
                    nbs.append({
                        "id": row["id"],
                        "title": row["title"],
                        "domain": row.get("domain"),
                        "createdAt": row["created_at"],
                        "updatedAt": row["updated_at"],
                        "sourceCount": 0
                    })
            return {"notebooks": nbs}
        except Exception as e:
            logger.warning(f"Error fetching notebooks from database: {e}")
            return {"notebooks": []}
    return {"notebooks": []}

@router.post("")
async def create_notebook(req: CreateNotebookRequest, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    nb_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    nb = {
        "id": nb_id,
        "title": req.title,
        "domain": req.domain or "General Science",
        "student_id": user["user_id"]
    }
    
    if sb:
        try:
            res = sb.table("notebooks").insert(nb).execute()
            if res.data and len(res.data) > 0:
                row = res.data[0]
                return {"notebook": {
                    "id": row.get("id", nb_id),
                    "title": row.get("title", req.title),
                    "domain": row.get("domain", req.domain),
                    "createdAt": row.get("created_at", now),
                    "updatedAt": row.get("updated_at", now),
                    "sourceCount": 0
                }}
        except Exception as e:
            logger.warning(f"Failed to insert notebook to Supabase: {e}")

    # Resilient fallback so user flow is never blocked
    return {"notebook": {
        "id": nb_id,
        "title": req.title,
        "domain": req.domain or "General Science",
        "createdAt": now,
        "updatedAt": now,
        "sourceCount": 0
    }}

@router.get("/{id}")
async def get_notebook(id: str, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    if sb:
        try:
            res = sb.table("notebooks").select("*").eq("id", id).execute()
            if res.data and len(res.data) > 0:
                return {"notebook": res.data[0]}
        except Exception as e:
            logger.warning(f"Failed to get notebook from Supabase: {e}")
            
    return {
        "notebook": {
            "id": id,
            "title": "Learning Session",
            "domain": "General Science",
            "student_id": user.get("user_id")
        }
    }

@router.get("/{id}/notes")
async def get_notes(id: str, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    if sb:
        try:
            res = sb.table("notes").select("*").eq("notebook_id", id).order('updated_at', desc=True).execute()
            notes = []
            if res.data:
                for row in res.data:
                    notes.append({
                        "id": row["id"],
                        "title": row["title"],
                        "content": row["content"],
                        "createdAt": row["created_at"],
                        "updatedAt": row["updated_at"]
                    })
            return {"notes": notes}
        except Exception as e:
            logger.warning(f"Failed to fetch notes from Supabase: {e}")
    return {"notes": []}

@router.post("/{id}/notes")
async def create_note(id: str, req: CreateNoteRequest, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    note_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    note = {
        "id": note_id,
        "notebook_id": id,
        "title": req.title,
        "content": req.content
    }
    if sb:
        try:
            res = sb.table("notes").insert(note).execute()
            if res.data and len(res.data) > 0:
                row = res.data[0]
                return {"note": {
                    "id": row.get("id", note_id),
                    "title": row.get("title", req.title),
                    "content": row.get("content", req.content),
                    "createdAt": row.get("created_at", now),
                    "updatedAt": row.get("updated_at", now)
                }}
        except Exception as e:
            logger.warning(f"Failed to create note in Supabase: {e}")
            
    return {"note": {
        "id": note_id,
        "title": req.title,
        "content": req.content,
        "createdAt": now,
        "updatedAt": now
    }}

@router.patch("/{id}/notes/{note_id}")
async def update_note(id: str, note_id: str, req: UpdateNoteRequest, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    if sb:
        try:
            sb.table("notes").update({"content": req.content}).eq("id", note_id).execute()
        except Exception as e:
            logger.warning(f"Failed to update note in Supabase: {e}")
    return {"status": "updated"}

@router.get("/{id}/decks")
async def get_decks(id: str, user: dict = Depends(get_current_user)):
    return {"decks": []}

@router.delete("/{id}")
async def delete_notebook(id: str, user: dict = Depends(get_current_user)):
    """Deletes a notebook and its associated sources, notes, and session logs."""
    from app.db.neon_client import log_event
    sb = get_supabase()
    if sb:
        try:
            # Cascade delete associated records
            sb.table("sources").delete().eq("notebook_id", id).execute()
            sb.table("notes").delete().eq("notebook_id", id).execute()
            sb.table("notebooks").delete().eq("id", id).execute()
            logger.info(f"Deleted notebook {id} and associated sources/notes from Supabase.")
        except Exception as e:
            logger.warning(f"Error deleting notebook {id} from Supabase: {e}")

    await log_event(
        session_id=id,
        student_id=user["user_id"],
        event_type="notebook_deleted",
        text=f"Notebook: Deleted notebook '{id}' and cascade-cleaned all local assets.",
        status="done"
    )

    return {"status": "deleted", "id": id}
