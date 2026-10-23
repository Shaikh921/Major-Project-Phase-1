from backend.app.core.config import settings, Settings, KNOWN_INSECURE_DEFAULT_SECRETS
import pytest


def test_application_name():
    assert settings.app_name == "Cloud Resource Monitoring & Intelligence Platform"


def test_application_version():
    assert settings.app_version == "0.1.0"


def test_environment():
    assert settings.app_env == "development"


@pytest.mark.parametrize("hardened_env", ["production", "prod", "staging", "stage", "lab", "pilot"])
def test_hardened_environments_reject_default_jwt_secret(hardened_env):
    """Verifies that staging, lab, and production all reject known default JWT signing secrets."""
    with pytest.raises(ValueError) as exc_info:
        Settings(
            environment=hardened_env,
            secret_key="cloudops-intel-secure-jwt-hmac-sha256-default-key-production-change-me",
        )
    err = str(exc_info.value)
    assert "Insecure or default SECRET_KEY detected" in err
    # Ensure secret is never printed in error message
    assert "cloudops-intel-secure" not in err


@pytest.mark.parametrize("hardened_env", ["production", "staging", "lab"])
def test_hardened_environments_reject_short_jwt_secret(hardened_env):
    """Verifies that secrets < 32 characters fail startup in hardened environments."""
    with pytest.raises(ValueError) as exc_info:
        Settings(
            environment=hardened_env,
            secret_key="too-short-secret-key-12345",
        )
    assert "SECRET_KEY is too short" in str(exc_info.value)


@pytest.mark.parametrize("hardened_env", ["production", "staging", "lab"])
def test_hardened_environments_accept_strong_secret(hardened_env):
    """Verifies that strong 32+ character secrets are accepted across hardened environments."""
    strong_key = "x" * 64
    s = Settings(
        environment=hardened_env,
        secret_key=strong_key,
    )
    assert s.environment == hardened_env
    assert s.secret_key == strong_key


def test_development_environment_permits_default_secret_for_local_workflow():
    """Verifies that local development mode remains functional with default secret."""
    dev = Settings(
        environment="development",
        secret_key="cloudops-intel-secure-jwt-hmac-sha256-default-key-production-change-me",
    )
    assert dev.environment == "development"
    