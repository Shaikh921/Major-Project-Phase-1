from backend.app.core.config import settings


def test_application_name():
    assert settings.app_name == "Cloud Resource Monitoring & Intelligence Platform"


def test_application_version():
    assert settings.app_version == "0.1.0"


def test_environment():
    assert settings.app_env == "development"
    