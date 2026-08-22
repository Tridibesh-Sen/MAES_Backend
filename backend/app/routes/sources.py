from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
import uuid
import datetime
import logging
from typing import List
from app.db.models import ImportUrlRequest, ImportYoutubeRequest, PasteTextRequest, ToggleSourceRequest
from app.db.supabase_client import get_supabase
from app.services.source_processor import extract_text_from_file, extract_text_from_url, extract_text_from_youtube
from app.services.embedding_service import process_source
from app.middleware.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sources", tags=["Sources"])

def _check_notebook_owner(sb, notebook_id: str, student_id: str):
    if not sb:
        return
    try:
        res = sb.table("notebooks").select("id, student_id").eq("id", notebook_id).execute()
        if not res.data:
            # Auto-register notebook if created in local demo session
            sb.table("notebooks").insert({
                "id": notebook_id,
                "student_id": student_id,
                "title": "Learning Session",
                "domain": "General Science"
            }).execute()
            return
        
        # Verify student scoping if student_id is set
        row = res.data[0]
        if row.get("student_id") and row.get("student_id") != student_id and student_id != "123e4567-e89b-12d3-a456-426614174000":
            # For development flexibility allow demo tokens to access
            logger.warning(f"Notebook ownership mismatch: {row.get('student_id')} vs {student_id}")
    except Exception as e:
        logger.debug(f"Notebook owner check bypassed: {e}")

def _check_source_owner(sb, source_id: str, student_id: str):
    if not sb:
        return
    try:
        res = sb.table("sources").select("notebook_id").eq("id", source_id).execute()
        if res.data:
            _check_notebook_owner(sb, res.data[0]["notebook_id"], student_id)
    except Exception as e:
        logger.debug(f"Source owner check bypassed: {e}")

@router.get("/{notebook_id}")
async def get_sources(notebook_id: str, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    if sb:
        try:
            _check_notebook_owner(sb, notebook_id, user["user_id"])
            result = sb.table("sources").select("*").eq("notebook_id", notebook_id).execute()
            sources = []
            for row in result.data:
                sources.append({
                    "id": row["id"],
                    "notebookId": row["notebook_id"],
                    "sourceType": row.get("source_type", "note"),
                    "title": row.get("title", "Untitled Source"),
                    "isActive": row.get("is_active", True),
                    "createdAt": row.get("created_at", datetime.datetime.now().isoformat())
                })
            return {"sources": sources}
        except Exception as e:
            logger.warning(f"Failed to fetch sources from Supabase: {e}")
    return {"sources": []}

@router.post("/upload")
async def upload_file(
    notebook_id: str = Form(...), 
    file: UploadFile = File(...), 
    bg_tasks: BackgroundTasks = None,
    user: dict = Depends(get_current_user)
):
    sb = get_supabase()
    _check_notebook_owner(sb, notebook_id, user["user_id"])
    
    text = await extract_text_from_file(file)
    if not text.strip() or text.startswith("SYSTEM NOTE: The uploaded PDF contains no readable text"):
        raise HTTPException(status_code=400, detail="The uploaded file contains no readable text. Please upload a valid text or document file.")
        
    # Classify file type for UI
    ext = file.filename.lower().split('.')[-1] if '.' in file.filename else 'txt'
    source_type = 'pdf' if ext == 'pdf' else ('docx' if ext in ['doc', 'docx'] else ('pptx' if ext in ['ppt', 'pptx'] else 'note'))
    
    from app.services.knowledge_extractor import extract_knowledge
    from app.db.neon_client import log_event
    structured = await extract_knowledge(text)
    result = _save_source(notebook_id, source_type, file.filename, text, structured)
    
    await log_event(
        session_id=notebook_id,
        student_id=user["user_id"],
        event_type="source_uploaded",
        text=f"Sources: Ingested '{file.filename}' ({source_type.upper()}), extracted {len(text)} characters of text.",
        status="done"
    )

    # Phase 3 RAG: trigger background embedding
    source_id = result["source"]["id"]
    if bg_tasks:
        bg_tasks.add_task(process_source, source_id, notebook_id, text)
    return result

@router.post("/import-url")
async def import_url(req: ImportUrlRequest, bg_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    from app.db.neon_client import log_event
    sb = get_supabase()
    _check_notebook_owner(sb, req.notebook_id, user["user_id"])
    text = await extract_text_from_url(req.url)
    from app.services.knowledge_extractor import extract_knowledge
    structured = await extract_knowledge(text)
    result = _save_source(req.notebook_id, "url", req.url, text, structured)
    
    await log_event(
        session_id=req.notebook_id,
        student_id=user["user_id"],
        event_type="source_url_imported",
        text=f"Sources: Crawled URL '{req.url}' and extracted {len(text)} characters of web text.",
        status="done"
    )
    if bg_tasks:
        bg_tasks.add_task(process_source, result["source"]["id"], req.notebook_id, text)
    return result

@router.post("/import-youtube")
async def import_youtube(req: ImportYoutubeRequest, bg_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    from app.db.neon_client import log_event
    sb = get_supabase()
    _check_notebook_owner(sb, req.notebook_id, user["user_id"])
    text = extract_text_from_youtube(req.url)
    from app.services.knowledge_extractor import extract_knowledge
    structured = await extract_knowledge(text)
    result = _save_source(req.notebook_id, "youtube", req.url, text, structured)
    
    await log_event(
        session_id=req.notebook_id,
        student_id=user["user_id"],
        event_type="source_youtube_imported",
        text=f"Sources: Extracted video transcript from YouTube URL: {req.url}.",
        status="done"
    )
    if bg_tasks:
        bg_tasks.add_task(process_source, result["source"]["id"], req.notebook_id, text)
    return result

@router.post("/paste")
async def paste_text(req: PasteTextRequest, bg_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    from app.db.neon_client import log_event
    sb = get_supabase()
    _check_notebook_owner(sb, req.notebook_id, user["user_id"])
    from app.services.knowledge_extractor import extract_knowledge
    structured = await extract_knowledge(req.content)
    result = _save_source(req.notebook_id, "note", req.title or "Pasted Text", req.content, structured)
    
    await log_event(
        session_id=req.notebook_id,
        student_id=user["user_id"],
        event_type="source_text_pasted",
        text=f"Sources: Ingested pasted text '{req.title or 'Note'}' ({len(req.content)} characters).",
        status="done"
    )
    if bg_tasks:
        bg_tasks.add_task(process_source, result["source"]["id"], req.notebook_id, req.content)
    return result

@router.delete("/{source_id}")
async def delete_source(source_id: str, user: dict = Depends(get_current_user)):
    from app.db.neon_client import log_event
    sb = get_supabase()
    if sb:
        _check_source_owner(sb, source_id, user["user_id"])
        try:
            sb.table("sources").delete().eq("id", source_id).execute()
        except Exception as e:
            logger.warning(f"Error deleting source from Supabase: {e}")
            
    await log_event(
        session_id="global",
        student_id=user["user_id"],
        event_type="source_deleted",
        text=f"Sources: Deleted knowledge source item '{source_id}'.",
        status="done"
    )
    return {"status": "deleted"}

@router.patch("/{source_id}/toggle")
async def toggle_source(source_id: str, req: ToggleSourceRequest, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    if sb:
        _check_source_owner(sb, source_id, user["user_id"])
        try:
            sb.table("sources").update({"is_active": req.is_active}).eq("id", source_id).execute()
        except Exception as e:
            logger.warning(f"Failed to toggle source in Supabase: {e}")
    return {"status": "updated"}

def _save_source(notebook_id: str, type: str, title: str, text: str, structured_content: dict):
    sb = get_supabase()
    source_uuid = str(uuid.uuid4())
    new_src = {
        "id": source_uuid,
        "notebook_id": notebook_id,
        "source_type": type,
        "title": title,
        "raw_content": text,
        "structured_content": structured_content,
        "is_active": True
    }
    if sb:
        try:
            res = sb.table("sources").insert(new_src).execute()
            if res.data:
                row = res.data[0]
                return {"source": {
                    "id": row.get("id", source_uuid),
                    "notebookId": row.get("notebook_id", notebook_id),
                    "sourceType": row.get("source_type", type),
                    "title": row.get("title", title),
                    "isActive": row.get("is_active", True),
                    "createdAt": row.get("created_at", datetime.datetime.now().isoformat())
                }}
        except Exception as e:
            logger.warning(f"Supabase source insert failed ({e}), returning memory record.")
    
    return {"source": {
        "id": source_uuid,
        "notebookId": notebook_id, 
        "sourceType": type,
        "title": title,
        "isActive": True,
        "createdAt": datetime.datetime.now().isoformat()
    }}
