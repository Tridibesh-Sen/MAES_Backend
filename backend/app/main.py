import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import session, turn, notebooks, sources, studio, audit, simulate
from app.middleware.rate_limiter import RateLimitingMiddleware
from app.db.neon_client import init_neon_pool, close_neon_pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_neon_pool()
    yield
    await close_neon_pool()

app = FastAPI(title="MAES Backend", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitingMiddleware)


app.include_router(session.router, prefix="/session", tags=["Session"])
app.include_router(turn.router, prefix="/turn", tags=["Turn"])
app.include_router(notebooks.router, tags=["Notebooks"])
app.include_router(sources.router, tags=["Sources"])
app.include_router(studio.router, tags=["Studio"])
app.include_router(audit.router, tags=["Audit"])
app.include_router(simulate.router, tags=["Simulation"])

# Track runtime invocation counters and live fallback state
runtime_agent_stats = {
    "agent_a": {"calls": 0, "status": "online", "model": "codestral-latest"},
    "agent_b": {"calls": 0, "status": "online", "model": "qwen/qwen3.8-27b"},
    "agent_p": {"calls": 0, "status": "online", "model": "codestral-latest"},
    "agent_s": {"calls": 0, "status": "online", "model": "ministral-8b-latest"},
    "dvs": {"calls": 0, "status": "online", "model": "qwen/qwen3.8-27b"},
    "last_active": None
}

def record_agent_execution(agent_name: str, status: str, model_name: str):
    """Updates runtime stats with exact model and online/fallback status."""
    if agent_name in runtime_agent_stats and isinstance(runtime_agent_stats[agent_name], dict):
        runtime_agent_stats[agent_name]["calls"] += 1
        runtime_agent_stats[agent_name]["status"] = status
        runtime_agent_stats[agent_name]["model"] = model_name
    runtime_agent_stats["last_active"] = agent_name

def increment_agent_call(agent_name: str):
    if agent_name in runtime_agent_stats and isinstance(runtime_agent_stats[agent_name], dict):
        runtime_agent_stats[agent_name]["calls"] += 1
    runtime_agent_stats["last_active"] = agent_name

@app.get("/")
def health_check():
    return {"status": "ok", "service": "MAES Backend"}

@app.get("/system-status")
async def get_system_status():
    """Returns live health and invocation status for all multi-agent components."""
    from app.config import settings
    from app.db.neon_client import get_neon_pool
    from app.db.supabase_client import get_supabase
    
    agent_a_key_ok = bool(settings.mistral_agent_a_key or settings.mistral_api_key)
    agent_b_key_ok = bool(settings.groq_agent_b_key or settings.groq_api_key)
    agent_p_key_ok = bool(settings.mistral_agent_p_key or settings.mistral_api_key)
    agent_s_key_ok = bool(settings.mistral_agent_s_key or settings.mistral_api_key)
    dvs_key_ok = bool(settings.groq_dvs_key or settings.groq_api_key)
    
    neon_ok = get_neon_pool() is not None
    supabase_ok = get_supabase() is not None
    upstash_ok = bool(settings.upstash_redis_rest_url and settings.upstash_redis_rest_token)
    gemini_ok = bool(settings.gemini_api_key)
    
    def get_status(agent_key: str, key_ok: bool) -> str:
        if not key_ok:
            return "offline"
        return runtime_agent_stats.get(agent_key, {}).get("status", "online")
    
    def get_model(agent_key: str, default_model: str) -> str:
        return runtime_agent_stats.get(agent_key, {}).get("model", default_model)

    is_online = agent_a_key_ok and agent_b_key_ok
    
    return {
        "status": "online" if is_online else "offline",
        "timestamp": sys.modules["datetime"].datetime.now().isoformat() if "datetime" in sys.modules else None,
        "agents": {
            "agent_a": {
                "name": "Agent A (Teacher)",
                "model": get_model("agent_a", settings.agent_a_model),
                "role": "Dynamic Scaffolding & Hint Generation",
                "usecase": "Formulates personalized Socratic prompts, conceptual analogies, and targeted scaffolding hints calibrated to the student's cognitive model and PID struggle score.",
                "trigger": "Executes on every active student dialogue turn.",
                "status": get_status("agent_a", agent_a_key_ok),
                "calls": runtime_agent_stats["agent_a"]["calls"]
            },
            "agent_b": {
                "name": "Agent B (Auditor)",
                "model": get_model("agent_b", settings.agent_b_model),
                "role": "Rubric Compliance & Non-Leakage Auditor",
                "usecase": "Validates Agent A drafts in real-time. Detects direct answer leakage, evaluates Bloom alignment, forces register switches, and triggers Peer or DVS agents.",
                "trigger": "Intercepts and audits every draft before final student transmission.",
                "status": get_status("agent_b", agent_b_key_ok),
                "calls": runtime_agent_stats["agent_b"]["calls"]
            },
            "agent_p": {
                "name": "Agent P (Peer Perspective)",
                "model": get_model("agent_p", settings.agent_p_model),
                "role": "Epistemic Misconception Conflict",
                "usecase": "Simulates a fellow student perspective to introduce cognitive conflict and challenge deep-seated misconceptions, prompting self-correction.",
                "trigger": "Triggered by Agent B when student exhibits Bloom stall >= 3 turns.",
                "status": get_status("agent_p", agent_p_key_ok),
                "calls": runtime_agent_stats["agent_p"]["calls"]
            },
            "agent_s": {
                "name": "Agent S (Fallback Agent)",
                "model": get_model("agent_s", settings.fallback_model),
                "role": "Emergency High-Availability Redundancy",
                "usecase": "Guarantees zero-downtime tutoring responses with sub-second fallback synthesis if primary models encounter rate limits or upstream timeouts.",
                "trigger": "Activated automatically on upstream latency or API failure.",
                "status": get_status("agent_s", agent_s_key_ok),
                "calls": runtime_agent_stats["agent_s"]["calls"]
            },
            "dvs": {
                "name": "DVS Visual Generator",
                "model": get_model("dvs", "qwen/qwen3.8-27b"),
                "role": "Inline Dynamic SVG Diagram Generator",
                "usecase": "Synthesizes custom vector diagrams, flowcharts, and structural SVG concept maps to ground complex abstract knowledge in visual intuition.",
                "trigger": "Triggered when CCLI typing telemetry indicates elevated cognitive load (> 0.70).",
                "status": get_status("dvs", dvs_key_ok),
                "calls": runtime_agent_stats["dvs"]["calls"]
            }
        },
        "infrastructure": {
            "neon": {"name": "Neon PostgreSQL", "usecase": "Serverless ACID database recording real-time telemetry, session progression, and instructor audit logs.", "status": "connected" if neon_ok else "offline"},
            "upstash": {"name": "Upstash Redis", "usecase": "Sub-millisecond REST distributed session cache, active turn contexts, and rate limiting.", "status": "connected" if upstash_ok else "offline"},
            "supabase": {"name": "Supabase Cloud", "usecase": "Auth user identity, pgvector source embeddings, and persistent notebook document stores.", "status": "connected" if supabase_ok else "offline"},
            "gemini": {"name": "Google Gemini RAG", "usecase": "Generates 768-dimensional dense vector embeddings for semantic document search.", "status": "connected" if gemini_ok else "offline"}
        }
    }

