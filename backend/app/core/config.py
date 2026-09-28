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

    # Security & Auth
    secret_key: str = "cloudops-intel-secure-jwt-hmac-sha256-default-key-production-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    verification_token_expire_hours: int = 24
    password_reset_token_expire_minutes: int = 30
    session_cookie_name: str = "cloudops_refresh_token"
    cookie_secure: bool = False  # Set to True in production (HTTPS)
    cookie_samesite: str = "lax"  # "lax", "strict", or "none"

    # CORS & Frontend Origins
    frontend_url: str = "http://127.0.0.1:8000"
    cors_origins: list[str] = [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://localhost:3000",
    ]

    # Optional First-Run Bootstrap Admin credentials
    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""

    # SMTP & Email Notification Settings
    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_tls: bool = True
    smtp_ssl: bool = False
    smtp_from_email: str = ""
    smtp_from_name: str = "CloudOps Intel Command Center"
    smtp_timeout_seconds: int = 10
    notify_super_admins_on_new_request: bool = True
    notify_on_critical_alerts: bool = False

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