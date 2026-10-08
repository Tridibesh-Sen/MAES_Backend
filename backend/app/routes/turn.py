"""
Turn Route (Phase 3): SSE Streaming + RAG + CCLI + GCD
Components: 3 (RAG retrieval), 4 (CLS injection), 5 (SSE streaming), 7 (GCD background)
"""
import json
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from groq import AsyncGroq

from app.db.models import TurnRequest
from app.db.upstash_client import get_session_context, set_session_context
from app.db.supabase_client import save_message, get_supabase
from app.db.neon_client import log_audit_entry
from app.agents.orchestrator import graph
from app.middleware.auth import get_current_user
from app.middleware.sanitizer import sanitize_student_input, wrap_for_llm
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/")
async def process_turn(
    req: TurnRequest,
    bg_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user)
):
    """
    Phase 3: Streaming SSE endpoint for a tutoring turn.
    Yields:
      event: status  — agent thinking indicators
      event: token   — streaming tokens of final hint
      event: dvs     — SVG visual scaffold (if triggered)
      event: done    — final bloom_tag, register, peer_challenge flag
    """
    context = await get_session_context(req.session_id)
    if not context:
        # Seamlessly auto-initialize session context on demand
        context = {
            "session_id": req.session_id,
            "student_id": user["user_id"],
            "domain": "General Science",
            "notebook_id": None,
            "turn_number": 1,
            "current_register": "socratic",
            "learner_model": {},
            "history": []
        }
        await set_session_context(req.session_id, context)
        
    # Ensure student scoping is aligned
    if context.get("student_id") != user["user_id"]:
        context["student_id"] = user["user_id"]
        await set_session_context(req.session_id, context)

    history = context.get("history", [])
    clean_message = sanitize_student_input(req.student_message)
    
    from app.middleware.sanitizer import check_guardrails
    is_safe, guard_warning = check_guardrails(clean_message)
    if not is_safe:
        async def guardrail_stream():
            yield f"event: token\ndata: {json.dumps({'token': guard_warning})}\n\n"
            yield f"event: done\ndata: {json.dumps({'bloom_tag': 'remember', 'register': 'socratic', 'peer_challenge': False, 'dvs_triggered': False})}\n\n"
        return StreamingResponse(guardrail_stream(), media_type="text/event-stream")

    learner_model = context.get("learner_model", {})
    # clean_message is sanitized of any malicious code/injection
    safe_message = clean_message

    # Fetch active misconception for Agent P seeding
    from app.services.gcd_service import get_active_misconception
    active_misconception = await get_active_misconception(user["user_id"])

    # --- Phase 3 Component 3: Semantic RAG retrieval ---
    notebook_id = context.get("notebook_id")
    active_sources = None
    
    if notebook_id:
        try:
            from app.services.embedding_service import retrieve_relevant_chunks
            chunks = retrieve_relevant_chunks(clean_message, notebook_id, top_k=5)
            if chunks:
                active_sources = "\n\n".join([f"[Chunk {i+1}]\n{c}" for i, c in enumerate(chunks)])
                logger.info(f"[TURN] Retrieved {len(chunks)} RAG chunks for notebook {notebook_id}")
            else:
                # Fallback: dump raw_content if embeddings not yet generated
                sb = get_supabase()
                if sb:
                    def fetch_sources():
                        return sb.table("sources").select("title, raw_content").eq("notebook_id", notebook_id).eq("is_active", True).execute()
                    res = await asyncio.to_thread(fetch_sources)
                    if res.data:
                        blocks = [f"--- SOURCE: {r['title']} ---\n{r.get('raw_content','')}" for r in res.data]
                        active_sources = "\n\n".join(blocks)[:3000]
        except Exception as e:
            logger.error(f"[TURN] RAG retrieval failed: {e}")

    # Compute PSI and Discrete PID Scaffolding Step
    from app.core.psi_engine import PSIEngine
    from app.core.scaffold_controller import PIDScaffoldController
    
    psi_engine = PSIEngine()
    psi_calc = psi_engine.compute_psi(
        latency_seconds=max(2.0, req.chronometric_load_score * 25.0),
        backspace_count=int(req.chronometric_load_score * 8.0),
        pause_count=1 if req.chronometric_load_score > 0.6 else 0,
        student_message=clean_message,
        concept_distance=0.0
    )
    observed_psi = psi_calc["psi"]

    controller = PIDScaffoldController(target_psi=0.40)
    # Replay prior turn errors if present in context
    u, pid_register, pid_telemetry = controller.compute_step(observed_psi)

    initial_state = {
        "session_id": req.session_id,
        "student_id": context.get("student_id"),
        "student_message": clean_message,
        "learner_model": context.get("learner_model", {}),
        "current_register": pid_register,
        "turn_number": context.get("turn_number", 1),
        "dialogue_history": history,
        "agent_a_draft": None,
        "agent_b_result": None,
        "agent_b_signal": None,
        "loop_count": 0,
        # Phase 3 & IEEE TLT CCLI + PID
        "chronometric_load_score": req.chronometric_load_score,
        "observed_psi": observed_psi,
        "control_output_u": u,
        "pid_error": pid_telemetry.get("error", 0.0),
        "bloom_stall_count": context.get("bloom_stall_count", 0),
        "active_misconception": active_misconception,
        "dvs_payload": None,
        "peer_challenge": False,
        "active_sources": active_sources,
        "audit_logs_to_dispatch": []
    }

    # Save student message to Supabase
    await asyncio.to_thread(save_message, req.session_id, "student", req.student_message)

    async def event_generator():
        try:
            # Status: Agent A thinking
            yield f"event: status\ndata: {json.dumps({'msg': 'Agent A is composing a response...'})}\n\n"
            
            from app.db.neon_client import log_event
            
            # Log CCLI
            load_label = "High Load" if req.chronometric_load_score > 0.7 else "Normal Load"
            await log_event(
                session_id=req.session_id,
                student_id=context.get("student_id", ""),
                event_type="ccli",
                text=f"CCLI: Analyzed passive chronometric typing load score: {req.chronometric_load_score:.2f} ({load_label}).",
                status="info"
            )
            
            # Log Orchestrator Start
            await log_event(
                session_id=req.session_id,
                student_id=context.get("student_id", ""),
                event_type="orchestrator",
                text="LangGraph Orchestrator: Initiating LangGraph pedagogical state machine.",
                status="info"
            )
            
            # Run orchestrator graph
            final_state = await graph.ainvoke(initial_state)
            
            # Status: streaming hint
            yield f"event: status\ndata: {json.dumps({'msg': 'Streaming response...'})}\n\n"

            hint = (final_state.get("agent_a_draft") or {}).get("hint_text", "I'm not sure how to respond.")
            bloom = (final_state.get("agent_b_result") or {}).get("bloom_tag_student", "remember")
            new_register = (final_state.get("agent_b_result") or {}).get("register_switch") or context.get("current_register", "socratic")
            dvs_payload = final_state.get("dvs_payload")
            peer_challenge = final_state.get("peer_challenge", False)

            # Phase 3 Component 5: Stream the hint word-by-word via Groq
            try:
                groq_key = settings.groq_agent_b_key or settings.groq_api_key
                if not groq_key:
                    raise ValueError("No Groq API key available for streaming")
                groq_client = AsyncGroq(api_key=groq_key)
                stream_model = settings.agent_b_model or "qwen/qwen3.8-27b"
                stream = await groq_client.chat.completions.create(
                    model=stream_model,
                    messages=[
                        {"role": "system", "content": "Restate the following hint clearly and naturally for a student. Do not change the meaning, and if the hint contains questions, a quiz, or a list, you MUST preserve them exactly. Output plain text only, no JSON."},
                        {"role": "user", "content": hint}
                    ],
                    temperature=0.3,
                    max_tokens=1000,
                    stream=True
                )
                streamed_hint = ""
                async for chunk in stream:
                    token = chunk.choices[0].delta.content or ""
                    if token:
                        streamed_hint += token
                        yield f"event: token\ndata: {json.dumps({'token': token})}\n\n"
                
                # Use streamed version as the saved hint
                hint = streamed_hint if streamed_hint else hint
            except Exception as e:
                logger.error(f"[TURN] Groq streaming failed, falling back to non-streamed: {e}")
                
                from app.db.neon_client import log_event
                await log_event(
                    session_id=req.session_id,
                    student_id=context.get("student_id", ""),
                    event_type="fallback",
                    text="Fallback LLM: Triggered due to generation timeout or streaming failure.",
                    status="alert"
                )
                
                # Fallback: send hint as single token
                yield f"event: token\ndata: {json.dumps({'token': hint})}\n\n"

            # Send DVS payload if triggered
            if dvs_payload:
                yield f"event: dvs\ndata: {json.dumps({'svg': dvs_payload})}\n\n"

            # Save tutor hint to Supabase
            await asyncio.to_thread(save_message, req.session_id, "tutor", hint)

            # Dispatch audit logs
            logs = final_state.get("audit_logs_to_dispatch", [])
            for log in logs:
                bg_tasks.add_task(log_audit_entry, **log)

            # Log pedagogy metrics to Neon
            from app.db.neon_client import get_neon_pool
            try:
                await log_event(
                    session_id=req.session_id,
                    student_id=context.get("student_id", ""),
                    event_type="dashboard",
                    text="Instructor Telemetry Dashboard: Syncing session metrics to Instructor Telemetry Dashboard.",
                    status="info"
                )
                
                pool = get_neon_pool()
                async with pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO pedagogy_metrics (session_id, student_id, turn_number, cls_score, bloom_stall_count, active_misconception)
                        VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                        req.session_id,
                        context.get("student_id", ""),
                        context.get("turn_number", 1),
                        req.chronometric_load_score,
                        context.get("bloom_stall_count", 0),
                        active_misconception
                    )
            except Exception as e:
                logger.error(f"[TURN] Failed to log pedagogy_metrics: {e}")

            # GCD background misconception detection
            bg_tasks.add_task(
                _detect_misconception_bg,
                req.session_id,
                context.get("student_id", ""),
                req.student_message,
                bloom
            )

            # Update context
            history.append({"role": "student", "text": req.student_message})
            history.append({"role": "tutor", "text": hint, "bloom_tag": bloom})
            context["history"] = history
            context["turn_number"] = context.get("turn_number", 1) + 1
            context["current_register"] = new_register
            
            # Track bloom stall: same bloom level → increment, different → reset
            prev_bloom = context.get("last_bloom_tag")
            if prev_bloom and prev_bloom == bloom:
                context["bloom_stall_count"] = context.get("bloom_stall_count", 0) + 1
            else:
                context["bloom_stall_count"] = 0
            context["last_bloom_tag"] = bloom
            
            await set_session_context(req.session_id, context)

            # Update student's persistent personalized learner model
            from app.db.supabase_client import update_learner_model
            bg_tasks.add_task(
                update_learner_model,
                context.get("student_id", ""),
                {
                    "preferred_style": new_register,
                    "last_active_turn": context.get("turn_number", 1),
                    "last_bloom_level": bloom
                }
            )

            # Done signal
            yield f"event: done\ndata: {json.dumps({'bloom_tag': bloom, 'register': new_register, 'peer_challenge': peer_challenge, 'dvs_triggered': dvs_payload is not None})}\n\n"

        except Exception as e:
            logger.error(f"[TURN] Graph execution error: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no"
    })


async def _detect_misconception_bg(session_id: str, student_id: str, message: str, bloom_tag: str):
    """Helper to call GCD service as a background task."""
    try:
        from app.services.gcd_service import detect_and_log_misconception
        from app.db.neon_client import log_event
        
        await detect_and_log_misconception(session_id, student_id, message, bloom_tag)
        
        await log_event(
            session_id=session_id,
            student_id=student_id,
            event_type="gcd",
            text="GCD: Background cognitive diagnosis completed. Active misconceptions updated.",
            status="success"
        )
    except Exception as e:
        logger.error(f"[TURN-BG] GCD detection failed: {e}")
