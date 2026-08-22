# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    secret_key: str = "dev-secret-key-change-in-production"
    
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_db_url: str = ""
    
    neon_database_url: str = ""
    
    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: str = ""
    
    # Global keys (loaded dynamically from .env)
    groq_api_key: str = ""
    mistral_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""

    # Per-Agent dedicated keys (loaded dynamically from .env)
    mistral_agent_a_key: str = ""
    mistral_agent_p_key: str = ""
    mistral_agent_s_key: str = ""
    groq_agent_b_key: str = ""
    groq_dvs_key: str = ""
    
    # Model selections
    agent_a_model: str = "mistral-large-latest"
    agent_b_model: str = "llama-3.3-70b-versatile"
    agent_p_model: str = "mistral-large-latest"
    fallback_model: str = "open-mistral-7b"
    
    session_ttl_minutes: int = 30

settings = Settings()
