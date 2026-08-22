"""
Phase 1 tests — updated to reflect Phase 3 architecture.

Key patch-location rules applied:
  - Patch at the location where the name is USED, not where it is defined.
  - async functions must be mocked with AsyncMock or new_callable=AsyncMock.
  - Inline imports (inside function bodies) are resolved from sys.modules,
    so patching the source module attribute is the correct approach.
"""
import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from app.main import app
from app.services.json_utils import repair_and_parse_json
from app.services.source_processor import extract_text_from_url

client = TestClient(app)

# Dummy demo user token — decoded by auth.py via jwt.get_unverified_claims()
DEMO_TOKEN = (
    "eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9"
    ".eyJzdWIiOiAiMTIzZTQ1NjctZTg5Yi0xMmQzLWE0NTYtNDI2NjE0MTc0MDAwIiwgInJvbGUiOiAiZGVtbyJ9"
    ".abcdefg123456789"
)
HEADERS = {"Authorization": f"Bearer {DEMO_TOKEN}"}

# PostgREST requires UUID format; plain strings like "nb-1" are rejected
VALID_NOTEBOOK_UUID = "123e4567-e89b-12d3-a456-426614174000"
VALID_SESSION_UUID  = "550e8400-e29b-41d4-a716-446655440000"
VALID_STUDENT_UUID  = "123e4567-e89b-12d3-a456-426614174001"


# ─── JSON repair utility ───────────────────────────────────────────────────────

def test_json_repair():
    assert repair_and_parse_json('{"key": "value"}') == {"key": "value"}
    assert repair_and_parse_json('{"key": "value",}') == {"key": "value"}
    assert repair_and_parse_json('```json\n{"key": "value"}\n```') == {"key": "value"}
    assert repair_and_parse_json('Here is your json: {"key": "value"}') == {"key": "value"}


# ─── Source processor: URL extraction ─────────────────────────────────────────
# extract_text_from_url is async and uses httpx.AsyncClient internally.
# We mock AsyncClient as an async context manager returning a fake response.
# asyncio.run() is used (Python 3.10+ deprecates get_event_loop() in sync context).

@patch("app.services.source_processor.httpx.AsyncClient")
def test_extract_text_from_url(mock_client_cls):
    mock_response = MagicMock()
    mock_response.text = (
        "<html><body><h1>Title</h1><p>Some text content.</p>"
        "<script>alert(1)</script></body></html>"
    )
    mock_response.raise_for_status.return_value = None

    mock_client_instance = AsyncMock()
    mock_client_instance.get = AsyncMock(return_value=mock_response)
    mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

    text = asyncio.run(extract_text_from_url("http://example.com"))
    assert "Title" in text
    assert "Some text content." in text
    assert "alert(1)" not in text


# ─── Session management ───────────────────────────────────────────────────────
# Patch functions at the routes.session module where they are imported/used.
# supabase calls inside create_session/end_session silently catch exceptions,
# so we patch the wrappers directly for clarity.

def test_session_start():
    with patch("app.routes.session.create_session") as mock_create, \
         patch("app.routes.session.get_learner_model", return_value={}) as _mock_lm, \
         patch("app.routes.session.set_session_context", new_callable=AsyncMock):
        mock_create.return_value = None
        response = client.post(
            "/session/start",
            json={"student_id": "stud-1", "domain": "Math"},
            headers=HEADERS,
        )
    assert response.status_code == 200
    assert "session_id" in response.json()


def test_session_end():
    with patch("app.routes.session.get_session_context", new_callable=AsyncMock, return_value=None), \
         patch("app.routes.session.db_end_session") as mock_end, \
         patch("app.routes.session.delete_session", new_callable=AsyncMock):
        mock_end.return_value = None
        response = client.post(
            "/session/end",
            json={"session_id": VALID_SESSION_UUID},
            headers=HEADERS,
        )
    assert response.status_code == 200
    assert response.json()["status"] == "ended"


# ─── Notebooks ─────────────────────────────────────────────────────────────────
# IMPORTANT: patch app.routes.notebooks.get_supabase — patching the definition
# (app.db.supabase_client.get_supabase) does NOT affect the already-bound name
# inside notebooks.py due to Python's import binding semantics.

@patch("app.routes.notebooks.get_supabase")
def test_get_notebooks(mock_get_sb):
    mock_sb = MagicMock()
    mock_get_sb.return_value = mock_sb

    # Chain: table("notebooks").select(...).eq(...).order(...).execute()
    chain = mock_sb.table.return_value
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.execute.return_value = MagicMock(data=[
        {
            "id": VALID_NOTEBOOK_UUID, "title": "Test", "domain": "Math",
            "created_at": "2023-01-01", "updated_at": "2023-01-01",
        }
    ])

    response = client.get("/notebooks", headers=HEADERS)
    assert response.status_code == 200
    assert len(response.json()["notebooks"]) == 1
    assert response.json()["notebooks"][0]["id"] == VALID_NOTEBOOK_UUID


@patch("app.routes.notebooks.get_supabase")
def test_create_notebook(mock_get_sb):
    mock_sb = MagicMock()
    mock_get_sb.return_value = mock_sb

    chain = mock_sb.table.return_value
    chain.insert.return_value = chain
    chain.execute.return_value = MagicMock(data=[
        {
            "id": VALID_NOTEBOOK_UUID, "title": "Calculus", "domain": "Mathematics",
            "created_at": "2023-01-01T00:00:00Z", "updated_at": "2023-01-01T00:00:00Z",
        }
    ])

    response = client.post(
        "/notebooks",
        json={"title": "Calculus", "domain": "Mathematics"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert "notebook" in response.json()
    assert response.json()["notebook"]["title"] == "Calculus"
    assert response.json()["notebook"]["id"] == VALID_NOTEBOOK_UUID


@patch("app.routes.notebooks.get_supabase")
def test_delete_notebook(mock_get_sb):
    mock_sb = MagicMock()
    mock_get_sb.return_value = mock_sb

    chain = mock_sb.table.return_value
    chain.delete.return_value = chain
    chain.eq.return_value = chain
    chain.execute.return_value = MagicMock(data=[])

    response = client.delete(f"/notebooks/{VALID_NOTEBOOK_UUID}", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"
    assert response.json()["id"] == VALID_NOTEBOOK_UUID


@patch("app.routes.sources.get_supabase")
@patch("app.services.knowledge_extractor.AsyncOpenAI")
def test_upload_source(mock_openai, mock_get_sb):
    mock_sb = MagicMock()
    mock_get_sb.return_value = mock_sb

    chain = mock_sb.table.return_value
    chain.select.return_value = chain
    chain.insert.return_value = chain
    chain.eq.return_value = chain
    chain.execute.return_value = MagicMock(data=[
        {
            "id": "src-123", "notebook_id": VALID_NOTEBOOK_UUID, "source_type": "note",
            "title": "notes.txt", "is_active": True, "created_at": "2023-01-01T00:00:00Z"
        }
    ])

    response = client.post(
        "/sources/upload",
        data={"notebook_id": VALID_NOTEBOOK_UUID},
        files={"file": ("notes.txt", b"Data Structures and Algorithms Notes", "text/plain")},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert "source" in response.json()
    assert response.json()["source"]["title"] == "notes.txt"


# ─── Studio: Flashcard generation ─────────────────────────────────────────────
# AsyncGroq must be patched at app.services.flashcard_gen (where it is instantiated),
# NOT at app.routes.studio (which never directly creates the client).
# get_supabase must be patched at app.routes.studio (where it is used).

@patch("app.services.flashcard_gen.AsyncGroq")
@patch("app.routes.studio.get_supabase")
def test_flashcard_gen(mock_get_sb, mock_groq):
    # --- Supabase mocks ---
    mock_sb = MagicMock()
    mock_get_sb.return_value = mock_sb

    def table_side_effect(table_name: str):
        tbl = MagicMock()
        if table_name == "sources":
            # _get_notebook_context: .select().eq().eq().execute()
            tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value = \
                MagicMock(data=[{"raw_content": "Machine learning is a field of AI..."}])
        elif table_name == "notebooks":
            # student_id lookup: .select().eq().execute()
            tbl.select.return_value.eq.return_value.execute.return_value = \
                MagicMock(data=[{"student_id": VALID_STUDENT_UUID}])
        elif table_name == "learner_models":
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif table_name == "sessions":
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif table_name == "messages":
            tbl.select.return_value.in_.return_value.order.return_value.execute.return_value = \
                MagicMock(data=[])
        return tbl

    mock_sb.table.side_effect = table_side_effect

    # --- Groq mock: returns exactly 1 flashcard ---
    mock_llm = AsyncMock()
    mock_llm.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(
            content='{"flashcards": [{"front": "What is ML?", "back": "Machine learning."}]}'
        ))]
    )
    mock_groq.return_value = mock_llm

    response = client.post(
        "/studio/flashcards",
        json={"notebook_id": VALID_NOTEBOOK_UUID},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert "deck" in response.json()
    assert len(response.json()["deck"]["cards"]) == 1


# ─── Turn: SSE chat turn ───────────────────────────────────────────────────────
# Phase 3 turn route uses:
#   - get_session_context (async, from upstash_client) → patch at routes.turn
#   - graph.ainvoke (LangGraph) → patch graph object at routes.turn
#   - get_neon_pool is imported inline inside event_generator() via
#     `from app.db.neon_client import get_neon_pool` → patch at app.db.neon_client
#   - AsyncGroq for streaming → patch at routes.turn
#   - save_message → patch at routes.turn
#   - set_session_context → patch at routes.turn
#   - detect_and_log_misconception (background task) → patch at gcd_service

@patch("app.routes.turn.graph")
@patch("app.routes.turn.get_session_context", new_callable=AsyncMock)
def test_chat_turn(mock_get_ctx, mock_graph):
    mock_get_ctx.return_value = {
        "student_id": "123e4567-e89b-12d3-a456-426614174000",
        "domain": "Math",
        "notebook_id": VALID_NOTEBOOK_UUID,
        "turn_number": 1,
        "current_register": "socratic",
        "history": [],
        "learner_model": {},
        "bloom_stall_count": 0,
    }

    mock_graph.ainvoke = AsyncMock(return_value={
        "agent_a_draft": {"hint_text": "Think about what the derivative represents..."},
        "agent_b_result": {
            "bloom_tag_student": "understand",
            "register_switch": None,
            "decision": "APPROVE",
        },
        "dvs_payload": None,
        "peer_challenge": False,
        "audit_logs_to_dispatch": [],
    })

    async def fake_groq_stream(*args, **kwargs):
        """Async generator that yields one streamed token chunk."""
        chunk = MagicMock()
        chunk.choices = [MagicMock(delta=MagicMock(content="Think about derivatives..."))]
        yield chunk

    with patch("app.routes.turn.save_message"), \
         patch("app.routes.turn.set_session_context", new_callable=AsyncMock), \
         patch("app.db.neon_client.get_neon_pool") as mock_pool, \
         patch("app.routes.turn.AsyncGroq") as mock_groq, \
         patch("app.services.gcd_service.detect_and_log_misconception", new_callable=AsyncMock):

        # Neon pool: async context manager mock
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_pool.return_value.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.return_value.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        # Groq streaming: create() must return an async iterable
        mock_groq.return_value.chat.completions.create = AsyncMock(
            return_value=fake_groq_stream()
        )

        response = client.post(
            "/turn/",
            json={
                "session_id": VALID_SESSION_UUID,
                "student_message": "What is a derivative?",
            },
            headers=HEADERS,
        )

    # The SSE StreamingResponse should return HTTP 200
    assert response.status_code == 200


# ─── Audit dashboard summary ───────────────────────────────────────────────────
# audit.py calls get_neon_pool() at the top of each route handler.
# Patch at app.routes.audit (where it is imported and used).

def test_audit_dashboard_summary():
    with patch("app.routes.audit.get_neon_pool") as mock_pool:
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {
                "session_id": VALID_SESSION_UUID,
                "student_id": "123e4567-e89b-12d3-a456-426614174000",
                "turns": 5,
                "avg_hint_quality": 0.85,
                "avg_bloom_alignment": 0.75,
            }
        ]
        mock_pool.return_value.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.return_value.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        response = client.get("/audit/dashboard/summary", headers=HEADERS)
        assert response.status_code == 200
        assert "sessions" in response.json()


# ─── Discrete PID Scaffold Controller ──────────────────────────────────────────

def test_pid_scaffold_controller():
    from app.core.scaffold_controller import PIDScaffoldController
    ctrl = PIDScaffoldController(target_psi=0.40, kp=0.85, ki=0.20, kd=0.15)
    
    # 1. Step response with high struggle (observed PSI = 0.80)
    u1, reg1, telem1 = ctrl.compute_step(0.80)
    assert u1 > 0.40
    assert reg1 in ["worked_example", "error_correction"]
    assert telem1["error"] == 0.40

    # 2. Step response with low struggle (observed PSI = 0.10)
    u2, reg2, telem2 = ctrl.compute_step(0.10)
    assert u2 < u1
    assert reg2 in ["socratic", "analogy_first"]


# ─── PSI Engine ───────────────────────────────────────────────────────────────

def test_psi_engine():
    from app.core.psi_engine import PSIEngine
    engine = PSIEngine(alpha=0.40, beta=0.35, gamma=0.25)
    
    res = engine.compute_psi(
        latency_seconds=15.0,
        backspace_count=5,
        pause_count=2,
        student_message="I think maybe the derivative is zero",
        concept_distance=0.20
    )
    assert 0.0 <= res["psi"] <= 1.0
    assert res["zone"] in ["low_struggle", "productive_struggle", "excessive_struggle"]
    assert "l_norm" in res["components"]


# ─── Epistemic Concept Graph & Decay ──────────────────────────────────────────

def test_epistemic_concept_graph():
    from app.core.epistemic_graph import EpistemicConceptGraph
    import datetime

    graph = EpistemicConceptGraph(review_threshold=0.50)
    graph.add_node("alg_01", "Algebra", domain="Math", decay_rate=0.05)
    graph.add_node("der_01", "Derivative", domain="Math", prerequisites=["alg_01"])

    # Simulate 30 days of elapsed time on prerequisite
    t_past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)
    graph.nodes["alg_01"].update_mastery(0.80, timestamp=t_past)

    # Decayed mastery should trigger diagnostic review
    diag = graph.check_diagnostic_review("der_01")
    assert diag["needs_review"] is True
    assert diag["weakest_prereq_id"] == "alg_01"

