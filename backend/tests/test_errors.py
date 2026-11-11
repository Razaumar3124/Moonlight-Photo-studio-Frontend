import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field

from app.core.exceptions import AppException, ResourceNotFoundException
from app.core.handlers import register_exception_handlers
from app.db.mongodb import MongoManager


class DummyRequest(BaseModel):
    name: str = Field(min_length=3)
    count: int = Field(gt=0)


def create_error_test_app() -> FastAPI:
    """Create a test application with routes designed to trigger various errors."""
    test_app = FastAPI()
    register_exception_handlers(test_app)
    router = APIRouter()

    @router.post("/test/validation")
    async def endpoint_validation(body: DummyRequest):
        return {"status": "ok", "data": body.model_dump()}

    @router.get("/test/custom-app-exception")
    async def endpoint_app_exception():
        raise AppException(
            message="Custom failure occurred",
            code="CUSTOM_TEST_CODE",
            status_code=400,
            details=[{"field": "sample_field", "issue": "sample issue description"}],
        )

    @router.get("/test/not-found")
    async def endpoint_not_found():
        raise ResourceNotFoundException(message="Test item not found", field="item_id")

    @router.get("/test/unhandled")
    async def endpoint_unhandled():
        # Deliberately raise unhandled divide by zero error
        return 1 / 0

    test_app.include_router(router)
    return test_app


@pytest.fixture
async def error_client() -> AsyncClient:
    app = create_error_test_app()
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_validation_error_envelope(error_client: AsyncClient):
    """Verify that validation failures return 422 with standard error envelope."""
    # Send invalid payload: name too short, count negative
    response = await error_client.post("/test/validation", json={"name": "a", "count": -5})
    assert response.status_code == 422

    data = response.json()
    assert "error" in data
    error = data["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"] == "Invalid request parameters"
    assert len(error["details"]) == 2

    fields = {d["field"] for d in error["details"]}
    assert "name" in fields
    assert "count" in fields
    assert "timestamp" in error


@pytest.mark.asyncio
async def test_custom_app_exception_envelope(error_client: AsyncClient):
    """Verify that custom domain AppException conforms to standard envelope."""
    response = await error_client.get("/test/custom-app-exception")
    assert response.status_code == 400

    data = response.json()
    assert "error" in data
    error = data["error"]
    assert error["code"] == "CUSTOM_TEST_CODE"
    assert error["message"] == "Custom failure occurred"
    assert error["details"] == [{"field": "sample_field", "issue": "sample issue description"}]


@pytest.mark.asyncio
async def test_resource_not_found_envelope(error_client: AsyncClient):
    """Verify that 404 ResourceNotFoundException returns standard envelope."""
    response = await error_client.get("/test/not-found")
    assert response.status_code == 404

    data = response.json()
    assert data["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert data["error"]["details"][0]["field"] == "item_id"


@pytest.mark.asyncio
async def test_unhandled_exception_does_not_leak_internals(error_client: AsyncClient):
    """Verify unhandled 500 exceptions return sanitized envelope without stack traces."""
    response = await error_client.get("/test/unhandled")
    assert response.status_code == 500

    data = response.json()
    assert "error" in data
    error = data["error"]
    assert error["code"] == "INTERNAL_SERVER_ERROR"
    assert error["message"] == "An unexpected internal server error occurred"
    # Ensure no Python traceback, file path, or exception name leaked in message
    assert "ZeroDivisionError" not in error["message"]
    assert "Traceback" not in str(data)


@pytest.mark.asyncio
async def test_mongo_manager_lifecycle():
    """Verify MongoManager connection initialization, retrieval guard, and cleanup."""
    manager = MongoManager()

    # Accessing database before connect raises DatabaseUnavailableException
    from app.core.exceptions import DatabaseUnavailableException

    with pytest.raises(DatabaseUnavailableException):
        manager.get_database()

    with pytest.raises(DatabaseUnavailableException):
        await manager.ping()

    # Disconnecting uninitialized manager does not throw
    await manager.disconnect()
