import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.logging import sanitize_sensitive_data


def test_default_settings():
    """Verify default configuration loads with expected defaults."""
    settings = Settings()
    assert settings.APP_NAME == "SAF Studio API"
    assert settings.VERSION == "0.1.0"
    assert settings.API_V1_STR == "/api/v1"
    assert settings.DATABASE_NAME == "saf_studio"
    assert settings.is_development is True
    assert settings.is_production is False


def test_comma_separated_cors_origins():
    """Verify comma-separated string is parsed into list of origins."""
    settings = Settings(CORS_ORIGINS="http://localhost:3000, https://saf.example.com")
    assert settings.CORS_ORIGINS == ["http://localhost:3000", "https://saf.example.com"]


def test_production_wildcard_cors_prohibited():
    """Verify wildcard CORS raises a ValidationError when ENVIRONMENT is production."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            CORS_ORIGINS=["*"],
        )
    assert "Wildcard or empty CORS_ORIGINS is forbidden in production" in str(exc_info.value)


def test_production_empty_cors_prohibited():
    """Verify empty CORS origins list raises a ValidationError in production."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            CORS_ORIGINS=[],
        )
    assert "Wildcard or empty CORS_ORIGINS is forbidden in production" in str(exc_info.value)


def test_sensitive_uri_masking():
    """Verify sensitive database credentials are masked in logs and strings."""
    secret_uri = "mongodb://admin_user:super_secret_pass@cluster0.mongodb.net:27017/saf_studio"
    sanitized = sanitize_sensitive_data(secret_uri)
    assert "super_secret_pass" not in sanitized
    assert "admin_user" not in sanitized
    assert "mongodb://***:***@cluster0.mongodb.net:27017/saf_studio" == sanitized


def test_invalid_environment_literal():
    """Verify invalid environment string fails validation."""
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="nonexistent_env")  # type: ignore[arg-type]


def test_mongodb_atlas_srv_url_valid():
    """Verify MongoDB Atlas SRV URI format is accepted."""
    srv_uri = "mongodb+srv://saf_admin:SecurePass123@cluster0.abcde.mongodb.net/saf_studio?retryWrites=true&w=majority"
    settings = Settings(MONGODB_URL=srv_uri)
    assert settings.MONGODB_URL == srv_uri


def test_mongodb_url_invalid_scheme():
    """Verify invalid URL scheme fails validation."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(MONGODB_URL="postgres://user:pass@localhost:5432/saf_studio")
    assert "MONGODB_URL must begin with either 'mongodb://'" in str(exc_info.value)


def test_mongodb_url_placeholder_rejection():
    """Verify placeholder <password> in connection string is rejected with clear error."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(MONGODB_URL="mongodb+srv://admin:<password>@cluster0.abcde.mongodb.net/saf_studio")
    assert "contains unresolved placeholder '<password>'" in str(exc_info.value)


def test_mongodb_timeout_default_is_10000():
    """Verify cloud default connection timeout is 10,000ms."""
    settings = Settings()
    assert settings.MONGODB_TIMEOUT_MS == 10000

