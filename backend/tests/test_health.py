import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_live_endpoint(client: AsyncClient):
    """Test that GET /api/v1/health/live returns 200 with service metadata."""
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "saf-studio-api"
    assert "version" in data
    assert isinstance(data["uptime_seconds"], (int, float))
    assert data["uptime_seconds"] >= 0


@pytest.mark.asyncio
async def test_health_live_independent_of_db(client: AsyncClient, mock_mongo_disconnected):
    """Test that GET /api/v1/health/live succeeds even when MongoDB is completely unreachable."""
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_ready_success(client: AsyncClient, mock_mongo_connected):
    """Test that GET /api/v1/health/ready returns 200 when MongoDB is connected."""
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ready"
    assert data["service"] == "saf-studio-api"
    assert data["database"]["connected"] is True
    assert data["database"]["status"] == "connected"
    assert data["database"]["latency_ms"] == 1.45
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_health_ready_failure_returns_503(client: AsyncClient, mock_mongo_disconnected):
    """Test that GET /api/v1/health/ready returns 503 and standard error envelope
    when MongoDB fails.
    """
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 503

    data = response.json()
    assert "error" in data
    error = data["error"]
    assert error["code"] == "DATABASE_UNAVAILABLE"
    assert "unreachable" in error["message"].lower() or "failed" in error["message"].lower()
    assert len(error["details"]) > 0
    assert error["details"][0]["field"] == "database"
    assert "timestamp" in error


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test root informational endpoint."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "SAF Studio Test API"
    assert data["health"] == "/api/v1/health/live"


@pytest.mark.asyncio
async def test_health_system_unified_endpoint(client: AsyncClient, mock_mongo_connected):
    """Test GET /api/v1/health returns comprehensive subsystem health."""
    response = await client.get("/api/v1/health")
    assert response.status_code in (200, 503)

    data = response.json()
    assert data["status"] in ("healthy", "degraded", "unhealthy")
    assert data["service"] == "saf-studio-api"
    assert "version" in data
    assert isinstance(data["uptime_seconds"], (int, float))
    assert "timestamp" in data

    components = data["components"]
    assert "database" in components
    assert components["database"]["connected"] is True
    assert components["database"]["status"] == "connected"

    assert "storage" in components
    assert "email" in components
    assert components["email"]["provider"] in ("mock", "resend")

    assert "whatsapp" in components
    assert "business_number" in components["whatsapp"]
    assert "public_app_url" in components["whatsapp"]

    assert "groq_ai" in components
    assert "enabled" in components["groq_ai"]

    assert "google_oauth" in components


@pytest.mark.asyncio
async def test_health_system_unhealthy_when_database_down(
    client: AsyncClient, mock_mongo_disconnected
):
    """Test GET /api/v1/health returns 503 and unhealthy status when MongoDB is unreachable."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 503

    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["components"]["database"]["connected"] is False
    assert "disconnected" in data["components"]["database"]["status"]


@pytest.mark.asyncio
async def test_health_ready_enriched_components(client: AsyncClient, mock_mongo_connected):
    """Test GET /api/v1/health/ready contains enriched component diagnostics."""
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ready"
    assert data["database"]["connected"] is True
    assert "storage" in data
    assert "email" in data
    assert "whatsapp" in data
    assert "groq_ai" in data
    assert "google_oauth" in data

