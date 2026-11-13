import pytest
from pydantic import ValidationError

from app.core.config import BACKEND_DIR, INSECURE_DEV_SECRET_KEY, Settings
from app.core.logging import sanitize_sensitive_data


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove the suite's pinned env vars so code defaults are what gets tested."""
    for name in Settings.model_fields:
        monkeypatch.delenv(name, raising=False)


def _production(**overrides) -> Settings:
    """A complete, valid production configuration (fake values) with optional overrides."""
    values = {
        "ENVIRONMENT": "production",
        "DEBUG": False,
        "RATE_LIMIT_BACKEND": "mongodb",
        "CORS_ORIGINS": ["https://moonlight.example.com"],
        "SECRET_KEY": "s" * 48,
        "OTP_SECRET_KEY": "o" * 48,
        "STORAGE_BACKEND": "r2",
        "R2_ACCOUNT_ID": "account",
        "R2_ACCESS_KEY_ID": "access",
        "R2_SECRET_ACCESS_KEY": "secret",
        "R2_BUCKET_NAME": "moonlight-studio-photos",
        "EMAIL_PROVIDER": "resend",
        "RESEND_API_KEY": "re_fake",
        "RESEND_FROM_EMAIL": "Moonlight <codes@moonlight.example.com>",
        "MONGODB_URL": "mongodb+srv://u:p@cluster0.abcde.mongodb.net/",
        "BUSINESS_WHATSAPP_NUMBER": "911234567890",
        "PUBLIC_APP_URL": "https://moonlight.example.com",
    }
    values.update(overrides)
    return Settings(**values)


def test_default_settings(clean_env):
    """Verify default configuration loads with expected Moonlight defaults."""
    settings = Settings()
    assert settings.APP_NAME == "Moonlight Photo Studio API"
    assert settings.VERSION == "0.1.0"
    assert settings.API_V1_STR == "/api/v1"
    assert settings.DATABASE_NAME == "moonlight_studio"
    assert settings.is_development is True
    assert settings.is_production is False


def test_comma_separated_cors_origins():
    """Verify comma-separated string is parsed into list of origins."""
    settings = Settings(CORS_ORIGINS="http://localhost:3000, https://moonlight.example.com")
    assert settings.CORS_ORIGINS == ["http://localhost:3000", "https://moonlight.example.com"]


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
    secret_uri = (
        "mongodb://admin_user:super_secret_pass@cluster0.mongodb.net:27017/moonlight_studio"
    )
    sanitized = sanitize_sensitive_data(secret_uri)
    assert "super_secret_pass" not in sanitized
    assert "admin_user" not in sanitized
    assert "mongodb://***:***@cluster0.mongodb.net:27017/moonlight_studio" == sanitized


def test_invalid_environment_literal():
    """Verify invalid environment string fails validation."""
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="nonexistent_env")  # type: ignore[arg-type]


def test_mongodb_atlas_srv_url_valid():
    """Verify MongoDB Atlas SRV URI format is accepted."""
    srv_uri = "mongodb+srv://moonlight_admin:SecurePass123@cluster0.abcde.mongodb.net/moonlight_studio?retryWrites=true&w=majority"
    settings = Settings(MONGODB_URL=srv_uri)
    assert settings.MONGODB_URL == srv_uri


def test_mongodb_url_invalid_scheme():
    """Verify invalid URL scheme fails validation."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(MONGODB_URL="postgres://user:pass@localhost:5432/moonlight_studio")
    assert "MONGODB_URL must begin with either 'mongodb://'" in str(exc_info.value)


def test_mongodb_url_placeholder_rejection():
    """Verify placeholder <password> in connection string is rejected with clear error."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            MONGODB_URL="mongodb+srv://admin:<password>@cluster0.abcde.mongodb.net/moonlight_studio"
        )
    assert "contains unresolved placeholder '<password>'" in str(exc_info.value)


def test_mongodb_timeout_default_is_10000(clean_env):
    """Verify cloud default connection timeout is 10,000ms."""
    settings = Settings()
    assert settings.MONGODB_TIMEOUT_MS == 10000


def test_defaults_are_safe_for_local_development(clean_env):
    """Defaults never point at a shared service or a real person."""
    settings = Settings()
    assert settings.STORAGE_BACKEND == "local"
    assert settings.EMAIL_PROVIDER == "mock"
    assert settings.GROQ_ENABLED is False
    assert settings.R2_BUCKET_NAME == "moonlight-studio-photos"
    assert settings.uses_insecure_dev_secret is True


def test_env_file_is_anchored_to_backend_dir():
    """The .env path doesn't depend on the working directory the server starts from."""
    assert Settings.model_config["env_file"] is None  # disabled by conftest for isolation
    from app.core import config

    assert config.BACKEND_DIR == BACKEND_DIR
    assert (BACKEND_DIR / "app" / "core" / "config.py").is_file()


def test_local_storage_root_resolves_relative_to_backend(clean_env):
    settings = Settings(LOCAL_STORAGE_PATH="storage/local")
    assert settings.local_storage_root == (BACKEND_DIR / "storage" / "local").resolve()


def test_valid_production_configuration_is_accepted():
    settings = _production()
    assert settings.is_production is True


def test_production_rejects_development_defaults(clean_env):
    """Production with defaults fails, naming every problem but no secret values."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(ENVIRONMENT="production", CORS_ORIGINS=["https://moonlight.example.com"])
    message = str(exc_info.value)
    for expected in (
        "SECRET_KEY",
        "OTP_SECRET_KEY",
        "STORAGE_BACKEND must be 'r2'",
        "EMAIL_PROVIDER must be 'resend'",
        "BUSINESS_WHATSAPP_NUMBER",
        "PUBLIC_APP_URL must use https://",
    ):
        assert expected in message
    assert INSECURE_DEV_SECRET_KEY not in message


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"SECRET_KEY": INSECURE_DEV_SECRET_KEY}, "SECRET_KEY must be a unique random value"),
        ({"SECRET_KEY": "short"}, "SECRET_KEY must be a unique random value"),
        ({"OTP_SECRET_KEY": "s" * 48}, "OTP_SECRET_KEY must be at least 32 characters"),
        ({"DEBUG": True}, "DEBUG must be false"),
        ({"R2_ACCESS_KEY_ID": ""}, "missing R2_ACCESS_KEY_ID"),
        ({"R2_ACCOUNT_ID": "", "R2_ENDPOINT_URL": ""}, "R2_ACCOUNT_ID (or R2_ENDPOINT_URL)"),
        (
            {"RESEND_FROM_EMAIL": "Moonlight <onboarding@resend.dev>"},
            "RESEND_FROM_EMAIL must use a domain verified in Resend",
        ),
        ({"EMAIL_PROVIDER": "mock"}, "EMAIL_PROVIDER must be 'resend'"),
        ({"BUSINESS_WHATSAPP_NUMBER": "919876543210"}, "BUSINESS_WHATSAPP_NUMBER is still the"),
        ({"LOG_LEVEL": "DEBUG"}, "LOG_LEVEL must not be DEBUG"),
        ({"COOKIE_SAMESITE": "none"}, "COOKIE_SAMESITE must not be 'none'"),
        ({"MONGODB_URL": "mongodb://localhost:27017"}, "MONGODB_URL must not point at localhost"),
        ({"HEALTH_DIAGNOSTICS_TOKEN": "short"}, "HEALTH_DIAGNOSTICS_TOKEN must be at least 16"),
        ({"PUBLIC_APP_URL": "http://moonlight.example.com"}, "PUBLIC_APP_URL must use https://"),
        ({"CORS_ORIGINS": ["http://moonlight.example.com"]}, "CORS_ORIGINS must all use https://"),
        ({"RATE_LIMIT_BACKEND": "memory"}, "RATE_LIMIT_BACKEND must be 'mongodb'"),
        ({"STORAGE_BACKEND": "local"}, "STORAGE_BACKEND must be 'r2'"),
        ({"GROQ_ENABLED": True, "GROQ_API_KEY": ""}, "GROQ_API_KEY is required"),
    ],
)
def test_production_requirement_violations(overrides, expected):
    with pytest.raises(ValidationError) as exc_info:
        _production(**overrides)
    assert expected in str(exc_info.value)


def test_list_settings_accept_comma_separated_env(clean_env, monkeypatch: pytest.MonkeyPatch):
    """Comma-separated env values used to crash pydantic-settings' JSON decoding."""
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example, https://b.example")
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.0/8,::1")
    settings = Settings()
    assert settings.CORS_ORIGINS == ["https://a.example", "https://b.example"]
    assert settings.TRUSTED_PROXIES == ["10.0.0.0/8", "::1"]


def test_list_settings_still_accept_json_env(clean_env, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CORS_ORIGINS", '["https://a.example"]')
    assert Settings().CORS_ORIGINS == ["https://a.example"]


def test_invalid_trusted_proxy_rejected(clean_env):
    with pytest.raises(ValidationError) as exc_info:
        Settings(TRUSTED_PROXIES=["10.0.0.0/8", "not-a-network"])
    assert "TRUSTED_PROXIES entry is not an IP or CIDR" in str(exc_info.value)


def test_refresh_cookie_path_defaults_and_validates(clean_env, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("REFRESH_COOKIE_PATH", "")  # as written by .env.example
    assert Settings().refresh_cookie_path == "/api/v1/auth"
    assert Settings(REFRESH_COOKIE_PATH="/v2/auth").refresh_cookie_path == "/v2/auth"
    with pytest.raises(ValidationError):
        Settings(REFRESH_COOKIE_PATH="auth")


def test_production_requires_shared_rate_limit_store():
    with pytest.raises(ValidationError) as exc_info:
        _production(RATE_LIMIT_BACKEND="memory")
    assert "RATE_LIMIT_BACKEND must be 'mongodb'" in str(exc_info.value)


def test_removed_tuning_variables_are_no_longer_settings():
    """Tuning knobs now live in app.core.limits; they cannot be changed through .env."""
    for name in (
        "GROQ_TIMEOUT_SECONDS",
        "GROQ_MAX_OUTPUT_TOKENS",
        "GROQ_DAILY_REQUEST_LIMIT",
        "GROQ_DAILY_TOKEN_BUDGET",
        "GROQ_MODEL",
        "R2_MAX_UPLOAD_MB",
        "QUOTE_PREVIEW_MAX_MB",
        "QUOTE_SHARE_EXPIRY_DAYS",
        "RESEND_TEST_MODE",
        "RESEND_TEST_RECIPIENT",
        "R2_CUSTOM_DOMAIN",
        "PASSWORD_RESET_TOKEN_EXPIRE_MINUTES",
    ):
        assert name not in Settings.model_fields, name


def test_stale_variables_in_an_old_env_file_are_ignored(clean_env, monkeypatch):
    monkeypatch.setenv("R2_MAX_UPLOAD_MB", "25")
    monkeypatch.setenv("RESEND_TEST_MODE", "true")
    settings = Settings()
    assert not hasattr(settings, "R2_MAX_UPLOAD_MB")


def test_fixed_free_tier_limits():
    from app.core import limits

    assert limits.EMAIL_DAILY_LIMIT == 100 and limits.EMAIL_WARN_AT == 95
    assert limits.R2_STORAGE_LIMIT_BYTES == 9_700_000_000
    assert limits.PHOTO_MAX_BYTES == 2 * 1024 * 1024
    assert limits.QUOTE_PREVIEW_MAX_BYTES == 2 * 1024 * 1024
    assert limits.GROQ_DAILY_REQUEST_LIMIT == 100 and limits.GROQ_DAILY_TOKEN_BUDGET == 50_000
