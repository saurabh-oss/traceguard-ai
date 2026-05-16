from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM provider — "groq" | "openai" | "anthropic"
    llm_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"

    langchain_api_key: str = ""
    langchain_project: str = "traceguard-ai"
    langchain_tracing_v2: str = "true"

    github_token: str = ""
    github_repo: str = ""

    database_url: str = "sqlite:///./traceguard.db"
    cors_origins: str = "http://localhost:5173"
    secret_key: str = "change-me"
    api_key: str = ""  # if set, all write endpoints require X-API-Key header

    # Notifications
    slack_webhook_url: str = ""  # post to this URL when a patch PR is ready

settings = Settings()