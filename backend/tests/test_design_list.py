import pytest
from httpx import AsyncClient

from tests.test_photo_upload import register_test_user


@pytest.mark.asyncio
async def test_list_designs_empty(client: AsyncClient):
    """EP-DSGN-04: User with no saved designs receives empty items array."""
    _, token = await register_test_user(client, "empty_designer@example.com")

    response = await client.get(
        "/api/v1/designs",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["total_pages"] == 0


@pytest.mark.asyncio
async def test_list_designs_isolation(client: AsyncClient):
    """EP-DSGN-04: User A cannot see designs created by User B."""
    _, token_a = await register_test_user(client, "designer_a@example.com")
    _, token_b = await register_test_user(client, "designer_b@example.com")

    # User A creates 2 designs
    await client.post(
        "/api/v1/designs",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"title": "Design A1"},
    )
    await client.post(
        "/api/v1/designs",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"title": "Design A2"},
    )

    # User B creates 1 design
    await client.post(
        "/api/v1/designs",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"title": "Design B1"},
    )

    # User A lists designs
    res_a = await client.get("/api/v1/designs", headers={"Authorization": f"Bearer {token_a}"})
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a["total"] == 2
    assert {it["title"] for it in data_a["items"]} == {"Design A1", "Design A2"}

    # User B lists designs
    res_b = await client.get("/api/v1/designs", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert data_b["total"] == 1
    assert data_b["items"][0]["title"] == "Design B1"


@pytest.mark.asyncio
async def test_list_designs_pagination_and_search(client: AsyncClient):
    """EP-DSGN-04: Test pagination parameters and title search filtering."""
    _, token = await register_test_user(client, "paginator_designer@example.com")

    for i in range(5):
        await client.post(
            "/api/v1/designs",
            headers={"Authorization": f"Bearer {token}"},
            json={"title": f"Gallery Wall {i + 1}"},
        )
    await client.post(
        "/api/v1/designs",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Dining Room Showcase"},
    )

    # Page 1 with page_size=2
    res_p1 = await client.get(
        "/api/v1/designs?page=1&page_size=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_p1.status_code == 200
    data_p1 = res_p1.json()
    assert data_p1["total"] == 6
    assert len(data_p1["items"]) == 2
    assert data_p1["page"] == 1
    assert data_p1["total_pages"] == 3

    # Search filter
    res_search = await client.get(
        "/api/v1/designs?search=Dining",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_search.status_code == 200
    data_search = res_search.json()
    assert data_search["total"] == 1
    assert data_search["items"][0]["title"] == "Dining Room Showcase"
