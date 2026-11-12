"""Phase 6: quotes tied to the saved design, retries, the WhatsApp link, report privacy."""

import asyncio
import json
import urllib.parse

import pytest
from httpx import AsyncClient

from tests.fakes import FakeQuoteRepository, FakeR2Storage
from tests.test_image_processing import make_test_image
from tests.test_photo_upload import register_test_user

API = "/api/v1"
KEY = "retry-key-0123456789"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _version_item(i: int) -> dict:
    return {
        "item_id": f"f{i}",
        "size_id": "12x16",
        "finish_id": "natural-oak",
        "orientation": "portrait",
        "sample_id": "frame-01",
        "position_x_inches": 20 + 20 * i,
        "position_y_inches": 30,
        "photo_width_inches": 12,
        "photo_height_inches": 16,
        "matting": {
            "enabled": True,
            "top_inches": 2,
            "bottom_inches": 2,
            "left_inches": 2,
            "right_inches": 2,
            "color_id": "museum-white",
        },
    }


def _quote_payload(design_id: str | None, count: int = 3) -> dict:
    return {
        "title": "Gallery",
        "designId": design_id,
        "displayUnit": "ft",
        "preview": {"sofa": True},
        "wall": {"widthIn": 144, "heightIn": 108, "paintId": "warm-cream"},
        "layout": {"style": "grid", "gapIn": 3},
        "frames": [
            {
                "id": f"f{i}",
                "sizeId": "12x16",
                "orientation": "portrait",
                "finishId": "natural-oak",
                "mount": {"enabled": True, "colourId": "museum-white", "marginIn": 2},
                "photo": {"kind": "sample", "sampleId": "frame-01"},
            }
            for i in range(count)
        ],
    }


async def _saved_design(client: AsyncClient, token: str, count: int = 3) -> str:
    design = await client.post(
        f"{API}/designs",
        headers=_auth(token),
        json={
            "title": "Gallery",
            "wall": {"width_inches": 144, "height_inches": 108, "paint_id": "warm-cream"},
        },
    )
    design_id = design.json()["id"]
    version = await client.post(
        f"{API}/designs/{design_id}/versions",
        headers=_auth(token),
        json={
            "layout_type": "grid",
            "items": [_version_item(i) for i in range(count)],
            "layout_metadata": {"style": "grid", "gap_inches": 3},
            "preview": {"sofa": True},
        },
    )
    assert version.status_code == 201, version.text
    return design_id


def _prepare(client: AsyncClient, token: str, payload: dict, key: str | None = None, preview=None):
    headers = _auth(token)
    if key:
        headers["Idempotency-Key"] = key
    return client.post(
        f"{API}/quotes/prepare",
        headers=headers,
        data={"design_data": json.dumps(payload)},
        files={"file": ("preview.png", preview or make_test_image(1200, 800, "PNG"), "image/png")},
    )


# ------------------------------------------------------------- saved design: ownership
@pytest.mark.asyncio
async def test_quote_for_a_saved_design_matching_what_is_quoted(client: AsyncClient):
    _, token = await register_test_user(client, "q-match@example.com")
    design_id = await _saved_design(client, token)
    res = await _prepare(client, token, _quote_payload(design_id))
    assert res.status_code == 201, res.text


@pytest.mark.asyncio
async def test_another_users_design_cannot_be_quoted(client: AsyncClient):
    _, owner = await register_test_user(client, "q-owner@example.com")
    _, other = await register_test_user(client, "q-other@example.com")
    design_id = await _saved_design(client, owner)
    res = await _prepare(client, other, _quote_payload(design_id))
    assert res.status_code == 403
    assert res.json()["error"]["details"][0]["field"] == "designId"
    assert "Gallery" not in res.text


@pytest.mark.asyncio
async def test_missing_or_deleted_designs_are_not_found(client: AsyncClient):
    _, token = await register_test_user(client, "q-gone@example.com")
    res = await _prepare(client, token, _quote_payload("0" * 24))
    assert res.status_code == 404
    design_id = await _saved_design(client, token)
    await client.delete(f"{API}/designs/{design_id}", headers=_auth(token))
    assert (await _prepare(client, token, _quote_payload(design_id))).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p["frames"].pop(),
        lambda p: p["frames"].append({**p["frames"][0], "id": "extra"}),
        lambda p: p["wall"].update(widthIn=200),
        lambda p: p["wall"].update(paintId="sand"),
        lambda p: p["layout"].update(style="row"),
        lambda p: p["frames"][0].update(sizeId="16x20"),
        lambda p: p["frames"][0].update(finishId="walnut"),
        lambda p: p["frames"][0].update(orientation="landscape"),
        lambda p: p["frames"][0]["mount"].update(marginIn=3),
        lambda p: p["frames"][0]["mount"].update(colourId="black"),
        lambda p: p["frames"][0]["mount"].update(enabled=False),
        lambda p: p["frames"][0].update(photo={"kind": "sample", "sampleId": "frame-02"}),
        lambda p: p["frames"][0].update(photo=None),
        lambda p: p["frames"][0].update(id="renamed"),
    ],
    ids=[
        "frame-removed",
        "frame-added",
        "wall-width",
        "paint",
        "layout",
        "size",
        "finish",
        "orientation",
        "mount-margin",
        "mount-colour",
        "mount-off",
        "photo",
        "photo-removed",
        "frame-id",
    ],
)
async def test_a_quote_that_differs_from_the_saved_design_is_refused(client: AsyncClient, mutate):
    """Unsaved edits can never end up in a report: the planner must save first."""
    _, token = await register_test_user(client, "q-stale@example.com")
    design_id = await _saved_design(client, token)
    payload = _quote_payload(design_id)
    mutate(payload)
    res = await _prepare(client, token, payload)
    assert res.status_code == 422, res.text
    error = res.json()["error"]
    assert error["details"][0]["field"] == "designId"
    assert "Save it" in error["message"]


@pytest.mark.asyncio
async def test_no_quote_row_or_upload_is_left_behind_by_a_refused_quote(
    client: AsyncClient, fake_quote_repo: FakeQuoteRepository, fake_r2_storage: FakeR2Storage
):
    _, token = await register_test_user(client, "q-clean@example.com")
    design_id = await _saved_design(client, token)
    before = len(fake_r2_storage.objects)
    payload = _quote_payload(design_id)
    payload["wall"]["widthIn"] = 200
    assert (await _prepare(client, token, payload)).status_code == 422
    assert fake_quote_repo.quotes == {}
    assert len(fake_r2_storage.objects) == before


@pytest.mark.asyncio
async def test_a_photo_swapped_after_saving_is_caught(client: AsyncClient):
    _, token = await register_test_user(client, "q-photo@example.com")
    ids = []
    for name in ("a.jpg", "b.jpg"):
        up = await client.post(
            f"{API}/photos/upload",
            headers=_auth(token),
            files={"file": (name, make_test_image(600, 800, "JPEG"), "image/jpeg")},
        )
        ids.append(up.json()["id"])
    design = await client.post(
        f"{API}/designs",
        headers=_auth(token),
        json={
            "title": "P",
            "wall": {"width_inches": 144, "height_inches": 108, "paint_id": "warm-cream"},
        },
    )
    design_id = design.json()["id"]
    item = {**_version_item(0), "photo_id": ids[0]}
    item.pop("sample_id")
    saved = await client.post(
        f"{API}/designs/{design_id}/versions",
        headers=_auth(token),
        json={"layout_type": "grid", "items": [item]},
    )
    assert saved.status_code == 201, saved.text

    payload = _quote_payload(design_id, count=1)
    payload["frames"][0]["photo"] = {"kind": "upload", "photoId": ids[0], "name": "a.jpg"}
    assert (await _prepare(client, token, payload)).status_code == 201
    payload["frames"][0]["photo"] = {"kind": "upload", "photoId": ids[1], "name": "b.jpg"}
    assert (await _prepare(client, token, payload)).status_code == 422
    payload["frames"][0]["photo"] = {"kind": "sample", "sampleId": "frame-01"}
    assert (await _prepare(client, token, payload)).status_code == 422


# ------------------------------------------------------------- idempotency
@pytest.mark.asyncio
async def test_a_retry_with_the_same_key_returns_the_same_quote(
    client: AsyncClient, fake_quote_repo: FakeQuoteRepository, fake_r2_storage: FakeR2Storage
):
    _, token = await register_test_user(client, "q-retry@example.com")
    design_id = await _saved_design(client, token)
    payload = _quote_payload(design_id)
    first = await _prepare(client, token, payload, key=KEY)
    second = await _prepare(client, token, payload, key=KEY)
    assert first.status_code == second.status_code == 201
    assert first.json()["quote_id"] == second.json()["quote_id"]
    assert len(fake_quote_repo.quotes) == 1
    assert len([k for k in fake_r2_storage.objects if k.startswith("quotes/")]) == 1
    # The link is re-issued: the first token no longer opens the report, the new one does.
    old = first.json()["report_url"].rsplit("/", 1)[1]
    new = second.json()["report_url"].rsplit("/", 1)[1]
    assert old != new
    assert (await client.get(f"{API}/quotes/share/{old}")).status_code == 404
    assert (await client.get(f"{API}/quotes/share/{new}")).status_code == 200


@pytest.mark.asyncio
async def test_concurrent_double_submits_create_one_quote(
    client: AsyncClient, fake_quote_repo: FakeQuoteRepository, fake_r2_storage: FakeR2Storage
):
    _, token = await register_test_user(client, "q-double@example.com")
    design_id = await _saved_design(client, token)
    payload = _quote_payload(design_id)
    results = await asyncio.gather(*(_prepare(client, token, payload, key=KEY) for _ in range(4)))
    assert {r.status_code for r in results} == {201}
    assert len({r.json()["quote_id"] for r in results}) == 1
    assert len(fake_quote_repo.quotes) == 1
    assert len([k for k in fake_r2_storage.objects if k.startswith("quotes/")]) == 1


@pytest.mark.asyncio
async def test_a_key_cannot_be_reused_for_a_different_design(client: AsyncClient):
    _, token = await register_test_user(client, "q-reuse@example.com")
    design_id = await _saved_design(client, token)
    await _prepare(client, token, _quote_payload(design_id), key=KEY)
    other = _quote_payload(None, count=2)
    res = await _prepare(client, token, other, key=KEY)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


@pytest.mark.asyncio
async def test_keys_are_per_user_and_expire(
    client: AsyncClient, fake_quote_repo: FakeQuoteRepository
):
    _, a = await register_test_user(client, "q-ka@example.com")
    _, b = await register_test_user(client, "q-kb@example.com")
    payload = _quote_payload(None)
    qa = await _prepare(client, a, payload, key=KEY)
    qb = await _prepare(client, b, payload, key=KEY)
    assert qa.json()["quote_id"] != qb.json()["quote_id"]  # B's key never returns A's quote
    # Age A's quote beyond the replay window: the key is no longer honoured.
    from datetime import UTC, datetime, timedelta

    for doc in fake_quote_repo.quotes.values():
        doc["created_at"] = datetime.now(UTC) - timedelta(minutes=30)
    res = await _prepare(client, a, payload, key=KEY)
    assert res.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "key", ["short", "has space 1234", "x" * 65, "bad/key/1234567", "<script>1234"]
)
async def test_malformed_idempotency_keys_are_rejected(client: AsyncClient, key: str):
    _, token = await register_test_user(client, "q-badkey@example.com")
    res = await _prepare(client, token, _quote_payload(None), key=key)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_without_a_key_each_request_still_creates_its_own_quote(
    client: AsyncClient, fake_quote_repo: FakeQuoteRepository
):
    _, token = await register_test_user(client, "q-nokey@example.com")
    await _prepare(client, token, _quote_payload(None))
    await _prepare(client, token, _quote_payload(None))
    assert len(fake_quote_repo.quotes) == 2


# ------------------------------------------------------------- WhatsApp link + report
@pytest.mark.asyncio
async def test_whatsapp_link_is_a_wa_me_chat_with_the_prefilled_message(client: AsyncClient):
    user, token = await register_test_user(client, "q-wa@example.com", "+919876543210")
    res = await _prepare(client, token, _quote_payload(None, count=4))
    url = res.json()["whatsapp_url"]
    parsed = urllib.parse.urlsplit(url)
    assert (parsed.scheme, parsed.netloc) == ("https", "wa.me")
    assert parsed.path.strip("/").isdigit()
    message = urllib.parse.parse_qs(parsed.query)["text"][0]
    assert "Moonlight Photo Studio" in message
    assert res.json()["quote_id"] in message
    assert "12 × 9 ft" in message and "Frames: 4" in message
    assert res.json()["report_url"] in message
    assert len(message) < 700  # concise: details live in the report
    assert "password" not in message.lower()


@pytest.mark.asyncio
async def test_report_matches_the_submitted_design_and_hides_private_data(client: AsyncClient):
    _, token = await register_test_user(client, "private.person@example.com", "+919876543210")
    design_id = await _saved_design(client, token, count=3)
    res = await _prepare(client, token, _quote_payload(design_id, count=3))
    share = res.json()["report_url"].rsplit("/", 1)[1]
    page = await client.get(f"{API}/quotes/share/{share}")
    html = page.text
    assert page.status_code == 200
    assert "12 × 9 ft" in html and "Natural Oak" in html and "Museum White (2 in border)" in html
    assert html.count("12 × 16 in") >= 3  # one row per frame
    # Private data: masked contact, no full e-mail or number, no internals.
    assert "private.person@example.com" not in html and "+919876543210" not in html
    for secret in (
        "share_token",
        "storage_key",
        "preview_image_key",
        "user_id",
        "Bearer",
        "/preview.png",
    ):
        assert secret not in html
    assert page.headers["referrer-policy"] == "no-referrer"
    assert "no-store" in page.headers["cache-control"]
    assert "default-src 'none'" in page.headers["content-security-policy"]
    image = await client.get(f"{API}/quotes/share/{share}/preview")
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"


@pytest.mark.asyncio
async def test_report_escapes_hostile_titles(client: AsyncClient):
    _, token = await register_test_user(client, "q-xss@example.com")
    payload = _quote_payload(None)
    payload["title"] = "<script>alert(1)</script><img src=x onerror=alert(2)>"
    payload["frames"][0]["photo"] = {
        "kind": "sample",
        "sampleId": "frame-01",
        "name": "<svg onload=alert(3)>",
    }
    res = await _prepare(client, token, payload)
    share = res.json()["report_url"].rsplit("/", 1)[1]
    html = (await client.get(f"{API}/quotes/share/{share}")).text
    assert "<script>alert(1)</script>" not in html and "<svg onload" not in html
    assert "&lt;script&gt;" in html


@pytest.mark.asyncio
async def test_expired_share_links_stop_working(
    client: AsyncClient, fake_quote_repo: FakeQuoteRepository
):
    from datetime import UTC, datetime, timedelta

    _, token = await register_test_user(client, "q-exp@example.com")
    res = await _prepare(client, token, _quote_payload(None))
    share = res.json()["report_url"].rsplit("/", 1)[1]
    assert (await client.get(f"{API}/quotes/share/{share}")).status_code == 200
    for doc in fake_quote_repo.quotes.values():
        doc["expires_at"] = datetime.now(UTC) - timedelta(seconds=1)
    assert (await client.get(f"{API}/quotes/share/{share}")).status_code == 404
    assert (await client.get(f"{API}/quotes/share/{share}/preview")).status_code == 404
