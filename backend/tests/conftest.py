"""Shared fixtures. The suite is hermetic: it never reads backend/.env (which may hold real
credentials), pins every integration to a safe offline value, and fails any test that tries
to reach a non-loopback host."""

import atexit
import os
import shutil
import socket
import tempfile

_TEST_STORAGE_ROOT = tempfile.mkdtemp(prefix="moonlight-test-storage-")
atexit.register(shutil.rmtree, _TEST_STORAGE_ROOT, ignore_errors=True)

# Set before any app module reads settings. Explicit values also override shell exports.
os.environ.update(
    {
        "ENVIRONMENT": "test",
        "MONGODB_URL": "mongodb://localhost:27017",
        "DATABASE_NAME": "moonlight_studio_test",
        "EMAIL_PROVIDER": "mock",
        "RESEND_API_KEY": "",
        "GROQ_ENABLED": "false",
        "GROQ_API_KEY": "",
        "GOOGLE_CLIENT_ID": "test-google-client-id.apps.googleusercontent.com",
        "STORAGE_BACKEND": "local",
        "RATE_LIMIT_BACKEND": "memory",
        "TRUSTED_PROXIES": "",
        "LOCAL_STORAGE_PATH": _TEST_STORAGE_ROOT,
        "R2_ACCOUNT_ID": "",
        "R2_ACCESS_KEY_ID": "",
        "R2_SECRET_ACCESS_KEY": "",
    }
)

from app.core.config import Settings

# pydantic-settings reads model_config at instantiation time, so this disables the .env
# file for every Settings() created in tests (including get_settings()).
Settings.model_config["env_file"] = None

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import (
    get_catalog_repository,
    get_design_repository,
    get_photo_repository,
    get_quote_repository,
    get_session_repository,
    get_storage,
    get_template_repository,
    get_user_repository,
)
from app.core.config import get_settings
from app.db.mongodb import mongo_manager
from app.main import create_application
from app.services.rate_limiter import rate_limiter
from tests.fakes import (
    FakeCatalogRepository,
    FakeDesignRepository,
    FakePhotoRepository,
    FakeQuoteRepository,
    FakeR2Storage,
    FakeSessionRepository,
    FakeTemplateRepository,
    FakeUserRepository,
    populate_fake_catalog,
)

get_settings.cache_clear()

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "testserver"}
_blocked_hosts: list[str] = []


def _host_name(host: object) -> str:
    return host.decode() if isinstance(host, bytes) else str(host)


_real_getaddrinfo = socket.getaddrinfo
_real_connect = socket.socket.connect


def _guarded_getaddrinfo(host, *args, **kwargs):
    if host is not None and _host_name(host) not in _LOOPBACK_HOSTS:
        _blocked_hosts.append(_host_name(host))
        raise socket.gaierror(f"Test suite blocked DNS lookup for {_host_name(host)}")
    return _real_getaddrinfo(host, *args, **kwargs)


def _guarded_connect(self, address):
    host = address[0] if isinstance(address, tuple) else address
    if _host_name(host) not in _LOOPBACK_HOSTS:
        _blocked_hosts.append(_host_name(host))
        raise ConnectionRefusedError(f"Test suite blocked connection to {_host_name(host)}")
    return _real_connect(self, address)


socket.getaddrinfo = _guarded_getaddrinfo
socket.socket.connect = _guarded_connect


@pytest.fixture(autouse=True)
def no_external_network():
    """Fail any test that attempted to reach a non-loopback host, even if the code under
    test swallowed the resulting error (health probes do)."""
    before = len(_blocked_hosts)
    yield
    attempted = _blocked_hosts[before:]
    assert not attempted, f"Test attempted external network access: {sorted(set(attempted))}"


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Test environment settings fixture."""
    return Settings(
        APP_NAME="Moonlight Photo Studio Test API",
        ENVIRONMENT="test",
        DEBUG=True,
        MONGODB_URL="mongodb://localhost:27017",
        DATABASE_NAME="moonlight_studio_test",
        MONGODB_TIMEOUT_MS=1000,
        CORS_ORIGINS=["http://localhost:5173"],
        LOG_LEVEL="DEBUG",
        SECRET_KEY="test-secret-key-32-chars-minimum-moonlight-studio-test-env",
        ACCESS_TOKEN_EXPIRE_MINUTES=30,
        REFRESH_TOKEN_EXPIRE_DAYS=14,
        PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=60,
        GOOGLE_CLIENT_ID="test-google-client-id.apps.googleusercontent.com",
        EMAIL_PROVIDER="mock",
        BUSINESS_WHATSAPP_NUMBER="919876543210",
    )


@pytest.fixture
def fake_user_repo() -> FakeUserRepository:
    """Isolated in-memory user repository for tests."""
    return FakeUserRepository()


@pytest.fixture
def fake_session_repo() -> FakeSessionRepository:
    """Isolated in-memory session repository for tests."""
    return FakeSessionRepository()


@pytest.fixture
def fake_catalog_repo() -> FakeCatalogRepository:
    """Isolated in-memory catalog repository populated with default data."""
    repo = FakeCatalogRepository()
    return repo


@pytest.fixture
def fake_template_repo() -> FakeTemplateRepository:
    """Isolated in-memory template repository populated with default data."""
    repo = FakeTemplateRepository()
    return repo


@pytest.fixture
def fake_photo_repo() -> FakePhotoRepository:
    """Isolated in-memory photo repository for tests."""
    return FakePhotoRepository()


@pytest.fixture
def fake_design_repo() -> FakeDesignRepository:
    """Isolated in-memory design repository for tests."""
    return FakeDesignRepository()


@pytest.fixture
def fake_quote_repo() -> FakeQuoteRepository:
    """Isolated in-memory quote repository for tests."""
    return FakeQuoteRepository()


@pytest.fixture
def fake_r2_storage() -> FakeR2Storage:
    """Isolated in-memory mock Cloudflare R2 object storage."""
    return FakeR2Storage()


@pytest.fixture(autouse=True)
def setup_default_catalogs(
    fake_catalog_repo: FakeCatalogRepository,
    fake_template_repo: FakeTemplateRepository,
):
    """Seed fake repositories before each test unless explicitly cleared."""
    populate_fake_catalog(fake_catalog_repo, fake_template_repo)
    yield


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Clear in-memory rate limiter buckets before and after each test."""
    rate_limiter.clear_all()
    yield
    rate_limiter.clear_all()


@pytest.fixture
def app(
    test_settings: Settings,
    fake_user_repo: FakeUserRepository,
    fake_session_repo: FakeSessionRepository,
    fake_catalog_repo: FakeCatalogRepository,
    fake_template_repo: FakeTemplateRepository,
    fake_photo_repo: FakePhotoRepository,
    fake_design_repo: FakeDesignRepository,
    fake_quote_repo: FakeQuoteRepository,
    fake_r2_storage: FakeR2Storage,
):
    """FastAPI test app instance with overridden dependencies."""
    application = create_application()
    application.dependency_overrides[get_settings] = lambda: test_settings
    application.dependency_overrides[get_user_repository] = lambda: fake_user_repo
    application.dependency_overrides[get_session_repository] = lambda: fake_session_repo
    application.dependency_overrides[get_catalog_repository] = lambda: fake_catalog_repo
    application.dependency_overrides[get_template_repository] = lambda: fake_template_repo
    application.dependency_overrides[get_photo_repository] = lambda: fake_photo_repo
    application.dependency_overrides[get_design_repository] = lambda: fake_design_repo
    application.dependency_overrides[get_quote_repository] = lambda: fake_quote_repo
    application.dependency_overrides[get_storage] = lambda: fake_r2_storage
    return application


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client that behaves like the frontend (sends the CSRF header)."""
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
        headers={"X-CSRF-Protection": "1"},
    ) as async_client:
        yield async_client


@pytest.fixture
async def raw_client(app) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client without the CSRF header (e.g. a cross-site form or script)."""
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as async_client:
        yield async_client


@pytest.fixture
def mock_mongo_connected():
    """Mock mongo_manager ping to simulate a healthy, connected MongoDB instance."""
    with patch.object(mongo_manager, "ping", new_callable=AsyncMock) as mock_ping:
        mock_ping.return_value = 1.45
        yield mock_ping


@pytest.fixture
def mock_mongo_disconnected():
    """Mock mongo_manager ping to simulate an unreachable database."""
    from app.core.exceptions import DatabaseUnavailableException

    with patch.object(mongo_manager, "ping", new_callable=AsyncMock) as mock_ping:
        mock_ping.side_effect = DatabaseUnavailableException(
            message="Database service is currently unreachable",
            issue="MongoDB ping timed out or refused connection",
        )
        yield mock_ping
