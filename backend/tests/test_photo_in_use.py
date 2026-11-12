import pytest
from httpx import AsyncClient

from tests.fakes import FakeR2Storage
from tests.test_image_processing import make_test_image
from tests.test_photo_upload import register_test_user

API = "/api/v1"


async def _upload(client: AsyncClient, token: str, name: str = "p.jpg") -> dict:
    res = await client.post(
        f"{API}/photos/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (name, make_test_image(width=600, height=800, fmt="JPEG"), "image/jpeg")},
    )
    assert res.status_code == 201, res.text
    return res.json()


async def _design_using(client: AsyncClient, token: str, photo_id: str, title: str = "Wall") -> str:
    headers = {"Authorization": f"Bearer {token}"}
    design = await client.post(f"{API}/designs", headers=headers, json={"title": title})
    design_id = design.json()["id"]
    res = await client.post(
        f"{API}/designs/{design_id}/versions",
        headers=headers,
        json={
            "layout_type": "custom",
            "items": [
                {
                    "item_id": "f1",
                    "size_id": "12x16",
                    "finish_id": "natural-oak",
                    "orientation": "portrait",
                    "photo_id": photo_id,
                    "position_x_inches": 40,
                    "position_y_inches": 30,
                    "photo_width_inches": 12,
                    "photo_height_inches": 16,
                }
            ],
        },
    )
    assert res.status_code == 201, res.text
    return design_id


@pytest.mark.asyncio
async def test_list_includes_signed_preview_and_thumbnail_urls(client: AsyncClient):
    _, token = await register_test_user(client, "urls@example.com")
    uploaded = await _upload(client, token)
    items = (
        await client.get(f"{API}/photos", headers={"Authorization": f"Bearer {token}"})
    ).json()["items"]
    assert items[0]["id"] == uploaded["id"]
    assert "/thumbnail?sig=" in items[0]["thumbnail_url"]
    assert "/preview?sig=" in items[0]["preview_url"]
    assert "&exp=" in items[0]["preview_url"]


@pytest.mark.asyncio
async def test_photo_used_by_a_saved_design_cannot_be_deleted(
    client: AsyncClient, fake_r2_storage: FakeR2Storage
):
    _, token = await register_test_user(client, "inuse@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    photo = await _upload(client, token)
    await _design_using(client, token, photo["id"])
    stored_before = len(fake_r2_storage.objects)

    res = await client.delete(f"{API}/photos/{photo['id']}", headers=headers)

    assert res.status_code == 409
    error = res.json()["error"]
    assert error["code"] == "PHOTO_IN_USE"
    assert "1 saved design" in error["message"]
    assert error["details"][0]["field"] == "id"
    # Nothing was removed: still listed, files intact, design not flagged missing.
    assert len(fake_r2_storage.objects) == stored_before
    listed = (await client.get(f"{API}/photos", headers=headers)).json()
    assert listed["total"] == 1


@pytest.mark.asyncio
async def test_in_use_message_counts_every_design(client: AsyncClient):
    _, token = await register_test_user(client, "inuse2@example.com")
    photo = await _upload(client, token)
    await _design_using(client, token, photo["id"], "One")
    await _design_using(client, token, photo["id"], "Two")
    res = await client.delete(
        f"{API}/photos/{photo['id']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 409
    assert "2 saved designs" in res.json()["error"]["message"]


@pytest.mark.asyncio
async def test_photo_can_be_deleted_once_no_live_design_uses_it(client: AsyncClient):
    _, token = await register_test_user(client, "freed@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    photo = await _upload(client, token)
    design_id = await _design_using(client, token, photo["id"])

    assert (await client.delete(f"{API}/photos/{photo['id']}", headers=headers)).status_code == 409
    assert (await client.delete(f"{API}/designs/{design_id}", headers=headers)).status_code == 204
    assert (await client.delete(f"{API}/photos/{photo['id']}", headers=headers)).status_code == 204


@pytest.mark.asyncio
async def test_unused_photo_still_deletes_and_others_cannot_probe_usage(client: AsyncClient):
    _, owner = await register_test_user(client, "owner-free@example.com")
    _, other = await register_test_user(client, "other-free@example.com")
    used = await _upload(client, owner, "used.jpg")
    free = await _upload(client, owner, "free.jpg")
    await _design_using(client, owner, used["id"])

    assert (
        await client.delete(
            f"{API}/photos/{free['id']}", headers={"Authorization": f"Bearer {owner}"}
        )
    ).status_code == 204
    # A different user gets the ownership error (403), never the "in use" detail.
    res = await client.delete(
        f"{API}/photos/{used['id']}", headers={"Authorization": f"Bearer {other}"}
    )
    assert res.status_code == 403
    assert "designs" not in res.text.lower().replace("designs.", "")
