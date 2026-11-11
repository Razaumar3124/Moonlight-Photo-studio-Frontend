import os

os.environ["ENVIRONMENT"] = "test"
os.environ["EMAIL_PROVIDER"] = "mock"

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import (
    get_catalog_repository,
    get_design_repository,
    get_photo_repository,
    get_quote_repository,
    get_r2_storage,
    get_session_repository,
    get_template_repository,
    get_user_repository,
)
from app.core.config import Settings, get_settings
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


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Test environment settings fixture."""
    return Settings(
        APP_NAME="SAF Studio Test API",
        ENVIRONMENT="test",
        DEBUG=True,
        MONGODB_URL="mongodb://localhost:27017",
        DATABASE_NAME="saf_studio_test",
        MONGODB_TIMEOUT_MS=1000,
        CORS_ORIGINS=["http://localhost:5173"],
        LOG_LEVEL="DEBUG",
        SECRET_KEY="test-secret-key-32-chars-minimum-saf-studio-test-env",
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
    application.dependency_overrides[get_r2_storage] = lambda: fake_r2_storage
    return application


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Asynchronous HTTP test client bound to ASGI transport."""
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
