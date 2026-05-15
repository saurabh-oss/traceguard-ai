from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    langchain_api_key: str = ""
    langchain_project: str = "traceguard-ai"
    langchain_tracing_v2: str = "true"
    github_token: str = ""
    github_repo: str = ""
    database_url: str = "sqlite:///./traceguard.db"
    cors_origins: str = "http://localhost:5173"
    secret_key: str = "change-me"

settings = Settings()