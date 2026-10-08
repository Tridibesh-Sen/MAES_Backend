from fastapi import APIRouter, Depends
import uuid
import datetime
from groq import AsyncGroq
from openai import AsyncOpenAI
from app.db.models import GenerateFlashcardsRequest, GenerateQuizRequest, GenerateStudyGuideRequest
from app.db.supabase_client import get_supabase, get_learner_model, get_student_history
from app.middleware.auth import get_current_user
from app.services.flashcard_gen import generate_flashcards
from app.services.quiz_gen import generate_quiz
from app.config import settings
from app.db.neon_client import log_event

router = APIRouter(prefix="/studio", tags=["Studio Generations"])

def _get_notebook_context(notebook_id: str) -> str:
    """Concatenates all active sources for a notebook to use as LLM context."""
    sb = get_supabase()
    if not sb:
        return ""
    try:
        res = sb.table("sources").select("title, raw_content").eq("notebook_id", notebook_id).eq("is_active", True).execute()
        if res.data:
            blocks = [f"--- SOURCE: {row.get('title', 'Document')} ---\n{row['raw_content']}" for row in res.data if row.get("raw_content")]
            return "\n\n".join(blocks)
    except Exception:
        pass
    return ""

@router.post("/flashcards")
async def create_flashcards(req: GenerateFlashcardsRequest, user: dict = Depends(get_current_user)):
    context = _get_notebook_context(req.notebook_id)
    student_id = user["user_id"]
    history = get_student_history(student_id)
    
    cards_data = await generate_flashcards(
        context=context, 
        topic=req.topic, 
        history=history,
        session_id=req.notebook_id,
        student_id=student_id
    )
    
    deck = {
        "id": str(uuid.uuid4()),
        "notebookId": req.notebook_id,
        "title": req.topic if req.topic else "Generated Flashcards",
        "createdAt": datetime.datetime.now().isoformat(),
        "cards": []
    }
    
    for i, c in enumerate(cards_data):
        deck["cards"].append({
            "id": str(uuid.uuid4()),
            "deckId": deck["id"],
            "front": c.get("front", ""),
            "back": c.get("back", ""),
            "status": "unseen",
            "sortOrder": i
        })
        
    return {"deck": deck}

@router.post("/quiz")
async def create_quiz(req: GenerateQuizRequest, user: dict = Depends(get_current_user)):
    context = _get_notebook_context(req.notebook_id)
    student_id = user["user_id"]
            
    # Load profile data from Supabase
    learner_model = get_learner_model(student_id)
    history = get_student_history(student_id)
    
    # Generate quiz personalized for the student's cognitive records and discussed themes
    quiz_data = await generate_quiz(
        context=context, 
        num_questions=req.num_questions, 
        difficulty=req.difficulty, 
        learner_model=learner_model, 
        history=history,
        session_id=req.notebook_id,
        student_id=student_id
    )
    
    questions = []
    for q in quiz_data:
        questions.append({
            "id": str(uuid.uuid4()),
            "question": q.get("question", ""),
            "options": q.get("options", []),
            "correct_index": q.get("correct_index", 0),
            "explanation": q.get("explanation", ""),
            "bloom_level": q.get("bloom_level", "understand")
        })
        
    return {"quiz": {"id": str(uuid.uuid4()), "questions": questions}}

@router.post("/study-guide")
async def create_study_guide(req: GenerateStudyGuideRequest, user: dict = Depends(get_current_user)):
    """Generates a structured markdown study guide using Groq LLaMA 3.3-70B with Mistral fallback."""
    context = _get_notebook_context(req.notebook_id)
    if not context:
        context = "Comprehensive foundational study guide covering key principles, concepts, and analytical frameworks."
    
    STUDY_GUIDE_SYSTEM = """You are an expert educational content creator. Generate a comprehensive, well-structured study guide from the provided source material.

The study guide MUST include:
1. ## Overview (2-3 sentence summary of the topic)
2. ## Key Concepts (bullet points of the most important ideas)
3. ## Detailed Notes (organized sections with explanations)
4. ## Common Misconceptions (things students often get wrong)
5. ## Practice Questions (3-5 questions with answers)
6. ## Summary (one-paragraph wrap-up)

Use clear markdown formatting. Be educational and comprehensive."""

    await log_event(
        session_id=req.notebook_id,
        student_id=user["user_id"],
        event_type="studio_guide_start",
        text="Studio: Generating structured Markdown study guide using Groq LLaMA 3.3 70B.",
        status="running"
    )

    try:
        client = AsyncGroq(api_key=settings.groq_agent_b_key or settings.groq_api_key)
        model_to_use = settings.agent_b_model or "qwen/qwen3.8-27b"
        response = await client.chat.completions.create(
            model=model_to_use,
            messages=[
                {"role": "system", "content": STUDY_GUIDE_SYSTEM},
                {"role": "user", "content": f"Generate a study guide from this source material:\n\n{context[:12000]}"}
            ],
            temperature=0.4,
            max_tokens=950
        )
        markdown_content = response.choices[0].message.content
        
        await log_event(
            session_id=req.notebook_id,
            student_id=user["user_id"],
            event_type="studio_guide_done",
            text="Studio: Successfully created structured Markdown study guide.",
            status="done"
        )
    except Exception as e:
        # Fallback to Mistral Large
        try:
            mistral_client = AsyncOpenAI(api_key=settings.mistral_agent_a_key or settings.mistral_api_key, base_url="https://api.mistral.ai/v1")
            response = await mistral_client.chat.completions.create(
                model=settings.agent_a_model,
                messages=[
                    {"role": "system", "content": STUDY_GUIDE_SYSTEM},
                    {"role": "user", "content": f"Generate a study guide from this source material:\n\n{context[:12000]}"}
                ],
                temperature=0.4,
                max_tokens=2500
            )
            markdown_content = response.choices[0].message.content
            await log_event(
                session_id=req.notebook_id,
                student_id=user["user_id"],
                event_type="studio_guide_fallback",
                text="Studio: Created Markdown study guide via Mistral Large fallback.",
                status="done"
            )
        except Exception as e2:
            markdown_content = f"# Study Guide\n\n## Overview\nStudy guide for current notebook.\n\n## Key Concepts\n- Review uploaded source materials.\n- Formulate questions for the Socratic AI tutor."

    return {
        "study_guide": {
            "id": str(uuid.uuid4()),
            "notebook_id": req.notebook_id,
            "markdown": markdown_content,
            "created_at": datetime.datetime.now().isoformat()
        }
    }
