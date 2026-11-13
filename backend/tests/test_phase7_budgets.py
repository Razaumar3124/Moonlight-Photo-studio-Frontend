"""Phase 7: daily email budget, storage budget, registration cap, maintenance, health caching.

Everything runs offline: Resend and storage are mocked, counters use the in-memory store
(the MongoDB store is exercised in test_live_mongo_budgets.py).
"""

import asyncio
import json
import logging
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from bson import ObjectId
from httpx import AsyncClient

from app.api.v1.endpoints.health import clear_probe_cache
from app.core import limits
from app.core.config import get_settings
from app.core.security import hash_password
from app.models.user import UserInDB
from app.services import usage_budget as ub
from app.services.email_service import EmailDeliveryException, EmailService, email_service
from app.services.image_processing_service import ImageProcessingService
from app.services.photo_service import PhotoService
from app.services.storage_maintenance import StorageMaintenance
from app.services.usage_budget import email_key, usage_budget
from tests.fakes import (
    FakePhotoRepository,
    FakeQuoteRepository,
    FakeR2Storage,
    FakeUserRepository,
)
from tests.test_image_processing import make_test_image
from tests.test_photo_upload import register_test_user
from tests.test_quote_prepare import make_valid_design_payload

API = "/api/v1"
RESEND_URL_FRAGMENT = "api.resend.com/emails"


@pytest.fixture
def settings_env(monkeypatch: pytest.MonkeyPatch, app):
    """Override settings through env vars for one test (affects get_settings() and SettingsDep)."""

    def apply(**values):
        for key, value in values.items():
            monkeypatch.setenv(key, str(value))
        get_settings.cache_clear()
        fresh = get_settings()
        app.dependency_overrides[get_settings] = lambda: fresh
        return fresh

    yield apply
    monkeypatch.undo()
    get_settings.cache_clear()


@pytest.fixture
def resend(settings_env):
    """Live Resend provider configuration (HTTP is always mocked)."""
    return settings_env(
        EMAIL_PROVIDER="resend",
        RESEND_API_KEY="re_fake_key_for_tests",
        RESEND_FROM_EMAIL="Moonlight <codes@moonlight.example.com>",
    )


@contextmanager
def resend_mock(post=None, get=None):
    """Replace the HTTP client the email service uses; yields call counters."""
    calls = SimpleNamespace(post=0, get=0)

    def respond(result):
        if isinstance(result, Exception):
            raise result
        return result

    class FakeHttpClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, *args, **kwargs):
            calls.post += 1
            return respond(post if post is not None else _ok_response())

        async def get(self, *args, **kwargs):
            calls.get += 1
            return respond(get if get is not None else _ok_response())

    with patch("app.services.email_service.httpx.AsyncClient", FakeHttpClient):
        yield calls


def _ok_response() -> httpx.Response:
    return httpx.Response(200, json={"id": "e1"}, request=httpx.Request("POST", "https://x"))


def _status(code: int) -> httpx.Response:
    return httpx.Response(code, json={"message": "x"}, request=httpx.Request("POST", "https://x"))


async def _preset(key: str, count: int) -> None:
    ok, _ = await usage_budget.store().reserve(key, count, 10**12)
    assert ok


# ============================================================ 1. email budget boundaries


@pytest.mark.parametrize(
    ("already_used", "allowed"), [(94, True), (95, True), (99, True), (100, False)]
)
async def test_email_slot_at_each_boundary(already_used: int, allowed: bool):
    await _preset(email_key(), already_used)
    assert await usage_budget.reserve_email() is allowed
    expected = already_used + (1 if allowed else 0)
    assert (await usage_budget.email_usage())["used"] == expected


async def test_the_101st_email_is_refused_and_100_are_allowed():
    results = [await usage_budget.reserve_email() for _ in range(101)]
    assert results[:100] == [True] * 100
    assert results[100] is False
    usage = await usage_budget.email_usage()
    assert usage["used"] == 100 and usage["remaining"] == 0 and usage["status"] == "exhausted"
    assert await usage_budget.email_exhausted() is True


async def test_warning_is_logged_at_95_but_sending_continues(caplog):
    await _preset(email_key(), 94)
    with caplog.at_level(logging.WARNING, logger="moonlight_studio.usage_budget"):
        assert await usage_budget.reserve_email() is True  # the 95th
    assert any("Email budget warning" in r.message for r in caplog.records)
    assert (await usage_budget.email_usage())["status"] == "warning"
    for _ in range(5):  # 96..100 still allowed
        assert await usage_budget.reserve_email() is True


async def test_concurrent_email_reservations_never_exceed_the_limit():
    results = await asyncio.gather(*(usage_budget.reserve_email() for _ in range(250)))
    assert sum(results) == 100
    assert (await usage_budget.email_usage())["used"] == 100


async def test_counter_resets_with_the_utc_day():
    with patch.object(ub, "utc_day", return_value="2026-11-12"):
        await _preset(email_key(), 100)
        assert await usage_budget.reserve_email() is False
    with patch.object(ub, "utc_day", return_value="2026-11-13"):
        assert await usage_budget.reserve_email() is True
        assert (await usage_budget.email_usage())["used"] == 1


async def test_release_never_goes_below_zero():
    await usage_budget.release_email()
    await usage_budget.release_email()
    assert (await usage_budget.email_usage())["used"] == 0


# ============================================================ 1b. failed sends and retries


async def _send(to: str = "customer@example.com") -> bool:
    return await EmailService().send_otp_email(to_email=to, otp_code="123456")


async def test_successful_send_uses_one_slot(resend):
    with resend_mock(post=_ok_response()):
        assert await _send() is True
    assert (await usage_budget.email_usage())["used"] == 1


@pytest.mark.parametrize("status_code", [401, 422, 429, 500, 503])
async def test_provider_rejection_gives_the_slot_back(resend, status_code):
    with resend_mock(post=_status(status_code)):
        with pytest.raises(EmailDeliveryException):
            await _send()
    assert (await usage_budget.email_usage())["used"] == 0


async def test_connection_failure_gives_the_slot_back(resend):
    with resend_mock(post=httpx.ConnectError("down")):
        with pytest.raises(EmailDeliveryException):
            await _send()
    assert (await usage_budget.email_usage())["used"] == 0


async def test_timeout_keeps_the_slot_because_the_email_may_have_been_sent(resend):
    with resend_mock(post=httpx.ReadTimeout("slow")):
        with pytest.raises(EmailDeliveryException):
            await _send()
    assert (await usage_budget.email_usage())["used"] == 1


async def test_exhausted_budget_blocks_before_any_http_call(resend):
    await _preset(email_key(), 100)
    with resend_mock() as post:
        with pytest.raises(Exception) as exc:
            await _send()
    assert post.post == 0
    assert getattr(exc.value, "code", "") == "EMAIL_DAILY_LIMIT_REACHED"


async def test_mock_provider_never_touches_the_budget():
    email_service.mock_sent_emails.clear()
    assert await _send() is True
    assert (await usage_budget.email_usage())["used"] == 0


# ============================================================ 1c. password reset endpoint


@pytest.fixture
async def reset_user(fake_user_repo: FakeUserRepository):
    now = datetime.now(UTC)
    await fake_user_repo.create(
        UserInDB(
            _id=str(ObjectId()),
            email="reset.me@example.com",
            phone="+919811100001",
            password_hash=hash_password("OriginalPassword123!"),
            full_name="Reset Me",
            role="customer",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
    )


def _forgot(client: AsyncClient, email: str):
    return client.post(f"{API}/auth/forgot-password", json={"email": email})


async def test_reset_request_uses_exactly_one_slot_for_a_real_account(
    client: AsyncClient, resend, reset_user
):
    with resend_mock(post=_ok_response()) as post:
        res = await _forgot(client, "reset.me@example.com")
    assert res.status_code == 200
    assert post.post == 1
    assert (await usage_budget.email_usage())["used"] == 1


async def test_unknown_address_uses_no_slot_and_looks_identical(
    client: AsyncClient, resend, reset_user
):
    with resend_mock(post=_ok_response()) as post:
        known = await _forgot(client, "reset.me@example.com")
        unknown = await _forgot(client, "nobody@example.com")
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert post.post == 1
    assert (await usage_budget.email_usage())["used"] == 1


async def test_failed_background_send_does_not_consume_the_allowance(
    client: AsyncClient, resend, reset_user
):
    with resend_mock(post=_status(500)):
        res = await _forgot(client, "reset.me@example.com")
    assert res.status_code == 200  # the response never reveals delivery problems
    assert (await usage_budget.email_usage())["used"] == 0


async def test_exhausted_allowance_gives_every_address_the_same_answer(
    client: AsyncClient, resend, reset_user
):
    await _preset(email_key(), 100)
    with resend_mock() as post:
        known = await _forgot(client, "reset.me@example.com")
        unknown = await _forgot(client, "nobody@example.com")
    assert post.post == 0
    assert known.status_code == unknown.status_code == 503
    assert (
        known.json()["error"]["code"]
        == unknown.json()["error"]["code"]
        == "EMAIL_DAILY_LIMIT_REACHED"
    )
    assert known.json()["error"]["message"] == unknown.json()["error"]["message"]
    assert "tomorrow" in known.json()["error"]["message"]


async def test_losing_the_race_for_the_last_slot_looks_like_an_unknown_account(
    client: AsyncClient, resend, reset_user, fake_session_repo
):
    await _preset(email_key(), 99)
    # Another worker takes slot 100 between the read-only check and our reservation.
    real_reserve = usage_budget.reserve_email

    async def reserve_after_rival():
        await real_reserve()
        return await real_reserve()

    with (
        patch.object(usage_budget, "reserve_email", reserve_after_rival),
        resend_mock() as post,
    ):
        res = await _forgot(client, "reset.me@example.com")
    assert res.status_code == 200
    assert post.post == 0
    assert await fake_session_repo.get_active_otp("reset.me@example.com") is None
    assert (await usage_budget.email_usage())["used"] == 100


async def test_requests_at_the_boundary_dispatch_until_100_then_stop(
    client: AsyncClient, resend, reset_user
):
    await _preset(email_key(), 99)
    with resend_mock(post=_ok_response()) as post:
        first = await _forgot(client, "reset.me@example.com")  # the 100th email
        assert first.status_code == 200
        assert post.post == 1
        second = await _forgot(client, "other@example.com")  # the 101st attempt
    assert second.status_code == 503
    assert post.post == 1
    assert (await usage_budget.email_usage())["used"] == 100


async def test_daily_per_address_cap_stops_repeat_requests(
    client: AsyncClient, settings_env, monkeypatch
):
    monkeypatch.setattr(limits, "FORGOT_PASSWORD_EMAIL_DAILY", 2)
    first = await _forgot(client, "same.person@example.com")
    second = await _forgot(client, "same.person@example.com")
    third = await _forgot(client, "same.person@example.com")
    assert (first.status_code, second.status_code) == (200, 200)
    assert third.status_code == 429


# ============================================================ 4. registration per IP per day


def _register(client: AsyncClient, n: int, email: str | None = None):
    return client.post(
        f"{API}/auth/register",
        json={
            "full_name": "Cap Tester",
            "email": email or f"cap{n}@example.com",
            "phone": f"+9198111{n:05d}",
            "password": "SecurePassword123!",
        },
    )


async def test_registration_cap_per_ip_per_day(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(limits, "REGISTER_DAILY_PER_IP", 3)
    codes = [(await _register(client, n)).status_code for n in range(4)]
    assert codes == [201, 201, 201, 429]
    blocked = await _register(client, 9)
    assert "Retry-After" in blocked.headers and int(blocked.headers["Retry-After"]) > 0
    assert blocked.json()["error"]["code"] == "REGISTRATION_LIMIT_REACHED"


async def test_failed_registrations_do_not_use_the_daily_cap(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(limits, "REGISTER_DAILY_PER_IP", 2)
    assert (await _register(client, 1)).status_code == 201
    for _ in range(3):  # duplicate email -> 409, not counted
        assert (await _register(client, 2, email="cap1@example.com")).status_code == 409
    assert (await _register(client, 3)).status_code == 201
    assert (await _register(client, 4)).status_code == 429


# ============================================================ 2. storage budget primitives


async def test_storage_reservation_boundaries(monkeypatch):
    monkeypatch.setattr(limits, "R2_STORAGE_LIMIT_BYTES", 1000)
    assert await usage_budget.reserve_storage(600) is True
    assert await usage_budget.reserve_storage(401) is False  # would be 1001
    assert await usage_budget.reserve_storage(400) is True  # exactly the ceiling
    assert await usage_budget.reserve_storage(1) is False
    assert await usage_budget.storage_used() == 1000
    await usage_budget.release_storage(400)
    assert await usage_budget.reserve_storage(1) is True


async def test_single_object_larger_than_the_ceiling_is_refused(monkeypatch):
    monkeypatch.setattr(limits, "R2_STORAGE_LIMIT_BYTES", 1000)
    assert await usage_budget.reserve_storage(1001) is False
    assert await usage_budget.storage_used() == 0


async def test_concurrent_storage_reservations_never_exceed_the_ceiling(monkeypatch):
    monkeypatch.setattr(limits, "R2_STORAGE_LIMIT_BYTES", 10_000)
    results = await asyncio.gather(*(usage_budget.reserve_storage(300) for _ in range(100)))
    assert sum(results) == 33  # 33 x 300 = 9900; the 34th would reach 10_200
    assert await usage_budget.storage_used() == 9900


async def test_default_ceiling_is_9_7_gb():
    assert limits.R2_STORAGE_LIMIT_BYTES == 9_700_000_000
    near = limits.R2_STORAGE_LIMIT_BYTES - 1_000_000
    await _preset(ub.STORAGE_KEY, near)
    assert await usage_budget.reserve_storage(1_000_000) is True
    assert await usage_budget.reserve_storage(1) is False


# ============================================================ 2b. uploads against the budget


async def _upload(client: AsyncClient, token: str, name="a.jpg", w=600, h=800, color="blue"):
    return await client.post(
        f"{API}/photos/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (name, make_test_image(w, h, "JPEG", color), "image/jpeg")},
    )


def _stored_bytes(storage: FakeR2Storage) -> int:
    return sum(len(v[0]) for v in storage.objects.values())


async def test_upload_counts_original_preview_and_thumbnail(
    client: AsyncClient, fake_r2_storage: FakeR2Storage
):
    _, token = await register_test_user(client, "bytes.count@example.com")
    assert (await _upload(client, token)).status_code == 201
    assert len(fake_r2_storage.objects) == 3
    assert await usage_budget.storage_used() == _stored_bytes(fake_r2_storage) > 0


async def test_upload_is_refused_when_it_would_pass_the_ceiling(
    client: AsyncClient, fake_r2_storage: FakeR2Storage, fake_photo_repo, monkeypatch
):
    _, token = await register_test_user(client, "full.bucket@example.com")
    monkeypatch.setattr(limits, "R2_STORAGE_LIMIT_BYTES", 500)
    res = await _upload(client, token)
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "STORAGE_LIMIT_REACHED"
    assert "full" in res.json()["error"]["message"].lower()
    assert fake_r2_storage.objects == {} and fake_photo_repo.photos == {}
    assert await usage_budget.storage_used() == 0


async def test_valid_uploads_are_accepted_until_the_ceiling_is_close(
    client: AsyncClient, fake_r2_storage: FakeR2Storage, monkeypatch
):
    _, token = await register_test_user(client, "room.left@example.com")
    assert (await _upload(client, token, "one.jpg")).status_code == 201
    one = await usage_budget.storage_used()
    monkeypatch.setattr(limits, "R2_STORAGE_LIMIT_BYTES", one * 2 + one // 2)
    assert (await _upload(client, token, "two.jpg")).status_code == 201
    assert (await _upload(client, token, "three.jpg")).status_code == 503
    # Deleting frees room again for a valid upload
    listing = await client.get(f"{API}/photos", headers={"Authorization": f"Bearer {token}"})
    first_id = listing.json()["items"][-1]["id"]
    deleted = await client.delete(
        f"{API}/photos/{first_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert deleted.status_code in (200, 204)
    assert (await _upload(client, token, "four.jpg")).status_code == 201


async def test_concurrent_uploads_near_the_ceiling_never_exceed_it(
    client: AsyncClient, fake_r2_storage: FakeR2Storage, monkeypatch
):
    _, token = await register_test_user(client, "race.upload@example.com")
    assert (await _upload(client, token, "probe.jpg")).status_code == 201
    one = await usage_budget.storage_used()
    # Reset: only room for two photos of this size
    fake_r2_storage.objects.clear()
    usage_budget.clear_all()
    monkeypatch.setattr(limits, "R2_STORAGE_LIMIT_BYTES", one * 2 + 50)
    results = await asyncio.gather(*(_upload(client, token, f"p{i}.jpg") for i in range(6)))
    codes = sorted(r.status_code for r in results)
    assert codes == [201, 201, 503, 503, 503, 503]
    assert await usage_budget.storage_used() == _stored_bytes(fake_r2_storage) <= one * 2 + 50


async def test_failed_upload_leaves_no_reservation(
    client: AsyncClient, fake_r2_storage: FakeR2Storage
):
    _, token = await register_test_user(client, "fail.upload@example.com")
    fake_r2_storage.should_fail_upload = True
    assert (await _upload(client, token)).status_code == 503
    assert fake_r2_storage.objects == {}
    assert await usage_budget.storage_used() == 0
    fake_r2_storage.should_fail_upload = False
    assert (await _upload(client, token)).status_code == 201  # retry works


async def test_partial_upload_is_rolled_back_completely(
    client: AsyncClient, fake_r2_storage: FakeR2Storage
):
    _, token = await register_test_user(client, "partial.upload@example.com")
    fake_r2_storage.fail_upload_after = 1  # original lands, preview fails
    assert (await _upload(client, token)).status_code == 503
    assert fake_r2_storage.objects == {}
    assert await usage_budget.storage_used() == 0


async def test_partial_upload_with_failed_cleanup_keeps_what_still_occupies_space(
    client: AsyncClient, fake_r2_storage: FakeR2Storage
):
    _, token = await register_test_user(client, "partial.stuck@example.com")
    fake_r2_storage.fail_upload_after = 1
    original_put = fake_r2_storage.put_object

    async def put_and_mark(key, data, content_type, metadata=None):
        result = await original_put(key, data, content_type, metadata)
        fake_r2_storage.fail_delete_keys.add(key)  # this object can't be removed afterwards
        return result

    fake_r2_storage.put_object = put_and_mark  # type: ignore[method-assign]
    assert (await _upload(client, token)).status_code == 503
    stuck = _stored_bytes(fake_r2_storage)
    assert stuck > 0
    assert await usage_budget.storage_used() == stuck  # still counted: it occupies space


async def test_metadata_failure_after_upload_releases_storage(
    client: AsyncClient, fake_r2_storage: FakeR2Storage, fake_photo_repo
):
    _, token = await register_test_user(client, "meta.fail@example.com")

    async def broken_create(photo):
        raise RuntimeError("mongo down")

    fake_photo_repo.create = broken_create  # type: ignore[method-assign]
    res = await _upload(client, token)
    assert res.status_code >= 500
    assert fake_r2_storage.objects == {}
    assert await usage_budget.storage_used() == 0


async def test_delete_frees_exactly_the_stored_bytes(
    client: AsyncClient, fake_r2_storage: FakeR2Storage
):
    _, token = await register_test_user(client, "delete.frees@example.com")
    first = (await _upload(client, token, "1.jpg", color="red")).json()["id"]
    await _upload(client, token, "2.jpg", color="green")
    both = await usage_budget.storage_used()
    res = await client.delete(f"{API}/photos/{first}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code in (200, 204)
    assert await usage_budget.storage_used() < both
    assert await usage_budget.storage_used() == _stored_bytes(fake_r2_storage)


async def test_failed_delete_is_remembered_and_retried_by_maintenance(
    client: AsyncClient,
    fake_r2_storage: FakeR2Storage,
    fake_photo_repo: FakePhotoRepository,
    fake_quote_repo: FakeQuoteRepository,
):
    _, token = await register_test_user(client, "delete.retry@example.com")
    photo_id = (await _upload(client, token)).json()["id"]
    used = await usage_budget.storage_used()
    stuck = [k for k in fake_r2_storage.objects if k.endswith("thumbnail.webp")]
    fake_r2_storage.fail_delete_keys = set(stuck)

    res = await client.delete(
        f"{API}/photos/{photo_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code in (200, 204)
    pending = fake_photo_repo.photos[photo_id]["purge_pending"]
    assert [p["key"] for p in pending] == stuck
    remaining = await usage_budget.storage_used()
    assert 0 < remaining < used  # only the thumbnail still counts

    fake_r2_storage.fail_delete_keys = set()
    service = PhotoService(fake_photo_repo, ImageProcessingService(), fake_r2_storage)
    maintenance = StorageMaintenance(fake_r2_storage, fake_photo_repo, fake_quote_repo, service)
    assert await maintenance.retry_pending_photo_deletes() == 1
    assert fake_r2_storage.objects == {}
    assert await usage_budget.storage_used() == 0
    assert fake_photo_repo.photos[photo_id]["purge_pending"] == []
    assert await maintenance.retry_pending_photo_deletes() == 0  # nothing double-released


# ============================================================ 2c. quote previews


def _prepare(client: AsyncClient, token: str, preview: bytes, key: str | None = None):
    headers = {"Authorization": f"Bearer {token}"}
    if key:
        headers["Idempotency-Key"] = key
    return client.post(
        f"{API}/quotes/prepare",
        headers=headers,
        data={"design_data": json.dumps(make_valid_design_payload())},
        files={"file": ("p.jpg", preview, "image/jpeg")},
    )


async def test_quote_preview_bytes_are_counted_and_replays_do_not_double_count(
    client: AsyncClient, fake_r2_storage: FakeR2Storage
):
    _, token = await register_test_user(client, "quote.bytes@example.com")
    preview = make_test_image(1600, 900, "JPEG")
    first = await _prepare(client, token, preview, key="key-12345678")
    assert first.status_code == 201, first.text
    assert await usage_budget.storage_used() == len(preview)
    replay = await _prepare(client, token, preview, key="key-12345678")
    assert replay.status_code in (200, 201)
    assert await usage_budget.storage_used() == len(preview)
    assert len(fake_r2_storage.objects) == 1


async def test_quote_is_refused_cleanly_when_storage_is_full(
    client: AsyncClient, fake_r2_storage: FakeR2Storage, fake_quote_repo, monkeypatch
):
    _, token = await register_test_user(client, "quote.full@example.com")
    monkeypatch.setattr(limits, "R2_STORAGE_LIMIT_BYTES", 100)
    res = await _prepare(client, token, make_test_image(1600, 900, "JPEG"))
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "STORAGE_LIMIT_REACHED"
    assert fake_quote_repo.quotes == {} and fake_r2_storage.objects == {}


async def test_quote_save_failure_releases_the_preview(
    client: AsyncClient, fake_r2_storage: FakeR2Storage, fake_quote_repo
):
    _, token = await register_test_user(client, "quote.rollback@example.com")
    fake_quote_repo.should_fail_create = True
    res = await _prepare(client, token, make_test_image(1600, 900, "JPEG"))
    assert res.status_code >= 500
    assert fake_r2_storage.objects == {}
    assert await usage_budget.storage_used() == 0


async def test_quote_preview_over_2_mb_is_rejected(client: AsyncClient):
    _, token = await register_test_user(client, "quote.big@example.com")
    res = await _prepare(client, token, b"\xff\xd8\xff" + b"0" * (2 * 1024 * 1024 + 100))
    assert res.status_code == 413


# ============================================================ 3. maintenance


def _maintenance(storage, photo_repo, quote_repo) -> StorageMaintenance:
    service = PhotoService(photo_repo, ImageProcessingService(), storage)
    return StorageMaintenance(storage, photo_repo, quote_repo, service)


async def _put(storage: FakeR2Storage, key: str, size: int, age_days: float) -> None:
    await storage.put_object(key, b"x" * size, "image/jpeg")
    storage.modified[key] = datetime.now(UTC) - timedelta(days=age_days)


async def test_sweep_removes_only_expired_quote_previews(
    fake_r2_storage, fake_photo_repo, fake_quote_repo
):
    await _put(fake_r2_storage, "quotes/u1/MQ-1/preview.jpg", 500, age_days=40)
    await _put(fake_r2_storage, "quotes/u1/MQ-2/preview.jpg", 700, age_days=5)
    await _put(fake_r2_storage, "users/u1/photos/p1/original.jpg", 900, age_days=400)
    await _preset(ub.STORAGE_KEY, 2100)
    maintenance = _maintenance(fake_r2_storage, fake_photo_repo, fake_quote_repo)

    assert await maintenance.sweep_expired_quote_previews() == 1
    assert set(fake_r2_storage.objects) == {
        "quotes/u1/MQ-2/preview.jpg",  # young: its report is still live
        "users/u1/photos/p1/original.jpg",  # customer photos are never swept
    }
    assert await usage_budget.storage_used() == 1600
    assert await maintenance.sweep_expired_quote_previews() == 0  # idempotent


async def test_sweep_keeps_a_preview_that_a_live_quote_still_uses(
    fake_r2_storage, fake_photo_repo, fake_quote_repo
):
    key = "quotes/u1/MQ-9/preview.jpg"
    await _put(fake_r2_storage, key, 500, age_days=40)
    fake_quote_repo.quotes["q9"] = {
        "preview_image_key": key,
        "expires_at": datetime.now(UTC) + timedelta(days=1),
    }
    maintenance = _maintenance(fake_r2_storage, fake_photo_repo, fake_quote_repo)
    assert await maintenance.sweep_expired_quote_previews() == 0
    assert key in fake_r2_storage.objects


async def test_sweep_failed_deletes_are_not_counted_as_freed(
    fake_r2_storage, fake_photo_repo, fake_quote_repo
):
    await _put(fake_r2_storage, "quotes/u1/MQ-1/preview.jpg", 500, age_days=40)
    await _put(fake_r2_storage, "quotes/u1/MQ-3/preview.jpg", 300, age_days=40)
    await _preset(ub.STORAGE_KEY, 800)
    fake_r2_storage.fail_delete_keys = {"quotes/u1/MQ-1/preview.jpg"}
    maintenance = _maintenance(fake_r2_storage, fake_photo_repo, fake_quote_repo)
    assert await maintenance.sweep_expired_quote_previews() == 1
    assert await usage_budget.storage_used() == 500  # the stuck object still counts


async def test_reconcile_corrects_drift_in_both_directions(
    fake_r2_storage, fake_photo_repo, fake_quote_repo
):
    await _put(fake_r2_storage, "users/u1/photos/p1/original.jpg", 1000, age_days=1)
    await _put(fake_r2_storage, "quotes/u1/MQ-5/preview.jpg", 500, age_days=1)
    maintenance = _maintenance(fake_r2_storage, fake_photo_repo, fake_quote_repo)

    await _preset(ub.STORAGE_KEY, 99_999)  # too high (e.g. lost releases)
    assert await maintenance.reconcile_counter() is True
    assert await usage_budget.storage_used() == 1500

    usage_budget.clear_all()  # too low (e.g. lost reservation)
    assert await maintenance.reconcile_counter() is True
    assert await usage_budget.storage_used() == 1500


async def test_reconcile_does_not_overwrite_a_counter_that_changed_during_measurement(
    fake_r2_storage, fake_photo_repo, fake_quote_repo
):
    await _put(fake_r2_storage, "users/u1/photos/p1/original.jpg", 1000, age_days=1)
    maintenance = _maintenance(fake_r2_storage, fake_photo_repo, fake_quote_repo)
    real_list = fake_r2_storage.list_objects

    async def list_while_upload_reserves(prefix=""):
        await usage_budget.reserve_storage(250)  # a concurrent upload reserves bytes
        return await real_list(prefix)

    fake_r2_storage.list_objects = list_while_upload_reserves  # type: ignore[method-assign]
    assert await maintenance.reconcile_counter(attempts=1) is False
    assert await usage_budget.storage_used() == 250  # untouched, not clobbered


async def test_run_once_runs_each_step_and_is_guarded_by_a_lease(
    fake_r2_storage, fake_photo_repo, fake_quote_repo
):
    await _put(fake_r2_storage, "quotes/u1/MQ-1/preview.jpg", 500, age_days=40)
    maintenance = _maintenance(fake_r2_storage, fake_photo_repo, fake_quote_repo)
    result = await maintenance.run_once()
    assert result["quote_previews_removed"] == 1 and result["counter_reconciled"] is True
    assert (await maintenance.run_once()) == {"skipped": True}  # another run holds the lease


async def test_one_failing_step_does_not_stop_the_others(
    fake_r2_storage, fake_photo_repo, fake_quote_repo
):
    maintenance = _maintenance(fake_r2_storage, fake_photo_repo, fake_quote_repo)

    async def boom(*_a, **_k):
        raise RuntimeError("storage down")

    maintenance.retry_pending_photo_deletes = boom  # type: ignore[method-assign]
    result = await maintenance.run_once()
    assert result["photo_deletes_retried"] is None
    assert result["counter_reconciled"] is True


# ============================================================ 2d. photo limits (2 MB, pixels)


async def test_photo_over_2_mb_is_rejected_with_a_clear_message(client: AsyncClient):
    _, token = await register_test_user(client, "two.mb@example.com")
    res = await client.post(
        f"{API}/photos/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("big.jpg", b"\xff\xd8\xff" + b"0" * (2 * 1024 * 1024 + 10), "image/jpeg")},
    )
    assert res.status_code == 413
    assert "2 MB" in res.json()["error"]["message"]


async def test_pixel_count_guard_rejects_huge_images_even_when_the_file_is_tiny(
    client: AsyncClient, fake_r2_storage
):
    _, token = await register_test_user(client, "pixels@example.com")
    huge = make_test_image(6000, 5000, "JPEG")  # 30 MP of one colour: a few KB
    assert len(huge) < 2 * 1024 * 1024
    res = await client.post(
        f"{API}/photos/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("huge.jpg", huge, "image/jpeg")},
    )
    assert res.status_code == 422
    assert "megapixels" in res.json()["error"]["message"]
    assert fake_r2_storage.objects == {}
    assert await usage_budget.storage_used() == 0


async def test_a_photo_just_under_the_pixel_cap_is_accepted(client: AsyncClient):
    _, token = await register_test_user(client, "pixels.ok@example.com")
    res = await _upload(client, token, w=4000, h=4000)  # 16 MP, one colour
    assert res.status_code == 201


# ============================================================ 4b. health: caching + usage


async def test_health_reuses_provider_probes_within_the_cache_window(
    client: AsyncClient, resend, mock_mongo_connected
):
    clear_probe_cache()
    ok = httpx.Response(200, json={}, request=httpx.Request("GET", "https://x"))
    with resend_mock(get=ok) as get:
        for _ in range(4):
            assert (await client.get(f"{API}/health")).status_code == 200
        calls_after_four = get.get
        clear_probe_cache()
        await client.get(f"{API}/health")
    assert calls_after_four == 1  # Resend key check happens once, not four times
    assert get.get == 2  # and again only after the cache expires


async def test_health_reports_usage_without_sensitive_data(
    client: AsyncClient, resend, mock_mongo_connected
):
    await _preset(email_key(), 96)
    await _preset(ub.STORAGE_KEY, 123_456)
    ok = httpx.Response(200, json={}, request=httpx.Request("GET", "https://x"))
    with resend_mock(get=ok):
        body = (await client.get(f"{API}/health")).json()
    usage = body["usage"]
    assert usage["email"]["used"] == 96 and usage["email"]["status"] == "warning"
    assert usage["email"]["limit"] == 100 and usage["email"]["remaining"] == 4
    assert usage["storage"]["used_bytes"] == 123_456
    assert usage["storage"]["limit_bytes"] == 9_700_000_000
    text = json.dumps(body)
    assert "re_fake_key_for_tests" not in text and "reset.me" not in text


async def test_health_usage_is_protected_like_the_rest_of_diagnostics(
    client: AsyncClient, settings_env
):
    settings_env(ENVIRONMENT="staging", HEALTH_DIAGNOSTICS_TOKEN="x" * 20)
    assert (await client.get(f"{API}/health")).status_code == 404
    assert (
        await client.get(f"{API}/health", headers={"X-Health-Token": "wrong" * 5})
    ).status_code == 404


def test_cache_helper_is_cleared_between_tests():
    clear_probe_cache()
