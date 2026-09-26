from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    app_name: str = "Cloud Resource Monitoring & Intelligence Platform"
    app_version: str = "0.1.0"
    app_env: str = "development"

    # General
    environment: str = "development"
    log_level: str = "INFO"
    debug: bool = True

    # Backend
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # Security
    secret_key: str = "change-this-in-production"

    # Database
    database_url: str = "sqlite:///./cloud_intelligence.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM providers
    openai_api_key: str = ""
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    default_llm_model: str = "gpt-4o-mini"

    # AWS
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_default_region: str = "us-east-1"

    # Frontend
    frontend_port: int = 3000
    next_public_api_base_url: str = "http://localhost:8000/api/v1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()