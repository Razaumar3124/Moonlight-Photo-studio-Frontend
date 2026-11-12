"""Phase 3 regression suite: catalog IDs, frontend ↔ backend contract, validation boundaries,
unit conversions, legacy data, quote calculations, preview formats and report branding."""

import json
import re
import urllib.parse
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.security import hash_token
from app.db.seed_catalog import SEED_MOLDINGS, SEED_TEMPLATES
from app.models.catalog import FrameColorOption
from app.models.design import DesignInDB, DesignWallInDB
from app.models.design_version import (
    BoundingBoxInDB,
    DesignItemInDB,
    DesignVersionInDB,
    MattingInDB,
)
from app.models.quote import (
    QuoteContactSnapshot,
    QuoteFrameSnapshot,
    QuoteInDB,
    QuoteWallSnapshot,
)
from app.models.template import LayoutTemplateInDB, TemplateSlotInDB
from app.modules import catalog
from app.modules.catalog import RULES
from app.services.email_service import render_otp_email_html
from tests.fakes import (
    FakeDesignRepository,
    FakeQuoteRepository,
    FakeR2Storage,
    FakeTemplateRepository,
)
from tests.test_image_processing import make_test_image
from tests.test_photo_upload import register_test_user

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src" / "features" / "memory-wall"
needs_frontend = pytest.mark.skipif(
    not (FRONTEND / "constants.ts").exists(), reason="frontend sources not present"
)


def _num(text: str) -> float:
    return float(text)


# =============================== Frontend contract ===============================


def _ts_constants() -> str:
    return (FRONTEND / "constants.ts").read_text(encoding="utf-8")


def _ts_block(source: str, name: str) -> str:
    # Bundled defaults are `export let` (the backend catalog replaces them at runtime).
    start = re.search(rf"export (?:const|let) {name}", source).start()
    # Up to the closing bracket of the array literal (not the `[]` in its type annotation).
    return source[start : source.index("\n]", start)]


@needs_frontend
def test_frame_sizes_match_frontend():
    block = _ts_block(_ts_constants(), "FRAME_SIZES")
    rows = re.findall(r"\{ id: '([^']+)', w: ([\d.]+), h: ([\d.]+), label: '([^']+)'", block)
    recommended = set(re.findall(r"id: '([^']+)'[^}]*recommended: true", block))
    assert [(s.id, s.width_inches, s.height_inches, s.label) for s in catalog.FRAME_SIZES] == [
        (i, _num(w), _num(h), label) for i, w, h, label in rows
    ]
    assert {s.id for s in catalog.FRAME_SIZES if s.recommended} == recommended


@needs_frontend
def test_finishes_mounts_and_paints_match_frontend():
    source = _ts_constants()
    finishes = re.findall(
        r"\{ id: '([^']+)', label: '([^']+)', hex: '([^']+)', profileIn: ([\d.]+) \}",
        _ts_block(source, "WOOD_FINISHES"),
    )
    assert [(f.id, f.label, f.hex, f.profile_inches) for f in catalog.FRAME_FINISHES] == [
        (i, label, hx, _num(p)) for i, label, hx, p in finishes
    ]
    swatch = re.compile(r"\{ id: '([^']+)', label: '([^']+)', hex: '([^']+)' \}")
    for name, items in (
        ("MOUNT_COLOURS", catalog.MOUNT_COLOURS),
        ("PAINT_SHADES", catalog.PAINT_SHADES),
    ):
        assert [(s.id, s.label, s.hex) for s in items] == swatch.findall(_ts_block(source, name))


@needs_frontend
def test_planner_rules_and_units_match_frontend():
    source = _ts_constants()

    def rule(key: str) -> float:
        return _num(re.search(rf"{key}: ([\d.]+)", source).group(1))

    def rng(key: str) -> tuple[float, float]:
        m = re.search(rf"{key}: \{{ min: ([\d.]+), max: ([\d.]+)", source)
        return _num(m.group(1)), _num(m.group(2))

    assert rule("eyeLevelIn") == RULES.eye_level_inches
    assert rule("wallMarginIn") == RULES.wall_margin_inches
    assert rule("minBottomIn") == RULES.min_bottom_inches
    assert rule("sofaClearanceIn") == RULES.sofa_clearance_inches
    assert rng("wallWidthIn") == (RULES.wall_width_min_inches, RULES.wall_width_max_inches)
    assert rng("wallHeightIn") == (RULES.wall_height_min_inches, RULES.wall_height_max_inches)
    assert rng("gapIn") == (RULES.gap_min_inches, RULES.gap_max_inches)
    assert rng("matIn") == (RULES.mat_min_inches, RULES.mat_max_inches)
    assert rng("frameCount") == (RULES.frame_count_min, RULES.frame_count_max)
    assert re.search(r"VARIANT_COUNT = (\d+)", source).group(1) == str(RULES.variant_count)

    # Sofa line: derived from the same room-photo measurements
    photo = {k: _num(v) for k, v in re.findall(r"(\w+Px|sofaWidthIn): ([\d.]+)", source)}
    px_per_in = (photo["sofaRightPx"] - photo["sofaLeftPx"]) / photo["sofaWidthIn"]
    sofa_top = (photo["heightPx"] - photo["sofaTopPx"]) / px_per_in
    assert abs(sofa_top - RULES.sofa_top_from_floor_inches) < 1e-9

    units = re.search(r"WALL_UNITS: readonly LengthUnit\[\] = \[([^\]]+)\]", source).group(1)
    assert re.findall(r"'(\w+)'", units) == list(catalog.WALL_UNITS)
    gaps = re.search(r"GAP_UNITS = \[([^\]]+)\]", source).group(1)
    assert re.findall(r"'(\w+)'", gaps) == list(catalog.GAP_UNITS)
    styles = re.findall(r"\{ id: '(\w+)', label: '(\w+)', apiCategory: '?(\w+)'? \}", source)
    assert [(i, label) for i, label, _ in styles] == list(catalog.LAYOUT_STYLE_LABELS.items())
    assert all(i == api for i, _, api in styles)  # UI style id == API category


@needs_frontend
def test_templates_match_frontend():
    source = (FRONTEND / "lib" / "templates.ts").read_text(encoding="utf-8")
    body = source[
        re.search(r"export (?:const|let) TEMPLATES", source).start() : source.index(
            "export const TEMPLATE_CATEGORIES"
        )
    ]
    blocks = re.split(r"\n  \{\n", body)[1:]
    token = re.compile(
        r"many\((\d+), '([^']+)'(?:, '(\w+)')?\)|\{ sizeId: '([^']+)', orientation: '(\w+)' \}"
    )
    frontend: dict[str, tuple[str, float, list[tuple[str, str]]]] = {}
    for block in blocks:
        tid = re.search(r"id: '([^']+)'", block).group(1)
        style = re.search(r"style: '(\w+)'", block).group(1)
        gap = _num(re.search(r"gapIn: ([\d.]+)", block).group(1))
        frames: list[tuple[str, str]] = []
        for m in token.finditer(block):
            if m.group(1):
                frames += [(m.group(2), m.group(3) or "portrait")] * int(m.group(1))
            else:
                frames.append((m.group(4), m.group(5)))
        frontend[tid] = (style, gap, frames)

    assert list(frontend) == list(catalog.TEMPLATE_IDS)
    assert [t["slug"] for t in SEED_TEMPLATES] == list(catalog.TEMPLATE_IDS)
    for seed in SEED_TEMPLATES:
        style, gap, frames = frontend[seed["slug"]]
        assert seed["category"] == style, seed["slug"]
        assert seed["gap_inches"] == gap, seed["slug"]
        slots = [
            catalog.size_for_dimensions(
                s["default_photo_width_inches"], s["default_photo_height_inches"]
            )
            for s in seed["slots"]
        ]
        assert [(m[0].id, m[1]) for m in slots] == frames, seed["slug"]
        assert seed["slots_count"] == len(frames)


ENDPOINTS_TS = FRONTEND.parents[1] / "services" / "endpoints.ts"


@pytest.mark.skipif(not ENDPOINTS_TS.exists(), reason="frontend sources not present")
def test_frontend_endpoint_map_matches_backend_routes(app):
    """Every path in frontend services/endpoints.ts exists in the backend's OpenAPI schema."""
    source = ENDPOINTS_TS.read_text(encoding="utf-8")
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)  # block comments
    source = re.sub(r"//[^\n]*", "", source)  # line comments (paths never contain //)
    literals = re.findall(r"'(/[^']*)'", source) + re.findall(r"`(/[^`]*)`", source)
    frontend = {re.sub(r"\$\{[^}]+\}", "{}", path) for path in literals}
    backend = {
        re.sub(r"\{[^}]+\}", "{}", path.removeprefix("/api/v1")) for path in app.openapi()["paths"]
    }
    assert frontend, "no paths parsed"
    assert frontend <= backend, f"unknown to the backend: {sorted(frontend - backend)}"


# ================================ Catalog endpoint ================================


async def test_get_catalog_publishes_ids_and_rules(client: AsyncClient):
    resp = await client.get("/api/v1/catalog")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "public, max-age=300"
    data = resp.json()
    assert [s["id"] for s in data["frame_sizes"]] == [s.id for s in catalog.FRAME_SIZES]
    assert [f["id"] for f in data["frame_finishes"]] == [f.id for f in catalog.FRAME_FINISHES]
    assert [m["id"] for m in data["mount_colors"]] == [m.id for m in catalog.MOUNT_COLOURS]
    assert [p["id"] for p in data["paint_shades"]] == [p.id for p in catalog.PAINT_SHADES]
    assert [s["id"] for s in data["layout_styles"]] == ["grid", "salon", "centre", "row"]
    assert data["template_ids"] == list(catalog.TEMPLATE_IDS)
    assert data["wall_units"] == ["ft", "in", "cm", "m"]
    rules = data["rules"]
    assert rules["wall_width_inches"] == {"min": 36.0, "max": 480.0}
    assert rules["wall_height_inches"] == {"min": 48.0, "max": 240.0}
    assert rules["frame_count"] == {"min": 1.0, "max": 16.0}
    assert rules["eye_level_inches"] == 60.0 and rules["min_bottom_inches"] == 12.0


async def test_frames_colours_carry_finish_ids(client: AsyncClient):
    resp = await client.get("/api/v1/frames")
    assert resp.status_code == 200
    items = {m["sku"]: m for m in resp.json()["items"]}
    oak = items["MOLD-OAK-BOX-100"]
    assert [c["id"] for c in oak["available_colors"]] == [f.id for f in catalog.FRAME_FINISHES]
    assert all(c["id"] for m in items.values() for c in m["available_colors"])
    assert len(SEED_MOLDINGS) == len(items)


def test_legacy_moulding_colour_without_id_gets_stable_id():
    legacy = FrameColorOption(name="Natural Oak", hex="#916843", profile_in=1.0)
    assert legacy.id == "natural-oak"
    assert FrameColorOption(id="walnut", name="Walnut", hex="#784E2D", profile_in=1).id == "walnut"


# ==================================== Templates ===================================


async def test_templates_use_planner_styles_and_slot_sizes(client: AsyncClient):
    data = (await client.get("/api/v1/templates")).json()
    assert {t["category"] for t in data["items"]} <= set(catalog.LAYOUT_STYLE_IDS)
    by_slug = {t["slug"]: t for t in data["items"]}
    assert by_slug["triptych"]["category"] == "row"
    assert by_slug["balanced-grid"]["gap_inches"] == 3.0
    assert by_slug["balanced-grid"]["slots"][0]["size_id"] == "12x16"
    assert by_slug["balanced-grid"]["slots"][0]["orientation"] == "portrait"
    first = by_slug["creative-salon"]["slots"][0]
    assert (first["size_id"], first["orientation"]) == ("16x20", "landscape")

    rows = (await client.get("/api/v1/templates?category=row")).json()["items"]
    assert {t["slug"] for t in rows} == {"minimal-row", "triptych", "panorama-row"}
    legacy_alias = (await client.get("/api/v1/templates?category=triptych")).json()["items"]
    assert {t["slug"] for t in legacy_alias} == {t["slug"] for t in rows}
    assert (await client.get("/api/v1/templates?category=staircase")).status_code == 422


async def test_legacy_template_documents_are_normalised(
    client: AsyncClient, fake_template_repo: FakeTemplateRepository
):
    legacy = LayoutTemplateInDB(
        slug="old-focal",
        name="Old Focal",
        description="Seeded before Phase 3",
        category="focal_center",
        min_wall_width_inches=60,
        min_wall_height_inches=50,
        recommended_wall_width_inches=90,
        recommended_wall_height_inches=80,
        slots_count=1,
        slots=[
            TemplateSlotInDB(
                slot_id="s1",
                relative_x_ratio=0.5,
                relative_y_ratio=0.5,
                default_photo_width_inches=9,
                default_photo_height_inches=13,
                aspect_ratio=0.69,
            )
        ],
        thumbnail_url="/static/templates/old.webp",
    )
    doc = legacy.model_dump(by_alias=True)
    doc.pop("gap_inches")  # documents written before the field existed
    fake_template_repo.templates[legacy.id] = doc

    items = (await client.get("/api/v1/templates?category=centre")).json()["items"]
    old = next(t for t in items if t["slug"] == "old-focal")
    assert old["category"] == "centre"
    assert old["gap_inches"] is None
    assert old["slots"][0]["size_id"] is None  # 9 x 13 isn't a catalog size
    assert old["slots"][0]["orientation"] == "portrait"


# ===================================== Units ======================================


@pytest.mark.parametrize(
    ("inches", "unit", "expected"),
    [
        (144, "ft", "12 ft"),
        (144, "in", "144 in"),
        (144, "cm", "366 cm"),
        (144, "m", "3.66 m"),
        (100, "ft", "8.3 ft"),
        (39.37, "m", "1 m"),
        (36, "mm", "914 mm"),
    ],
)
def test_format_length_matches_frontend(inches, unit, expected):
    assert catalog.format_length(inches, unit) == expected


def test_unit_round_trip_and_wall_size():
    for unit in catalog.ACCEPTED_WALL_UNITS:
        assert abs(catalog.to_inches(catalog.from_inches(123.4, unit), unit) - 123.4) < 1e-9
    assert catalog.to_inches(3.6576, "m") == pytest.approx(144)
    assert catalog.format_wall_size(144, 108, "ft") == "12 × 9 ft"
    assert catalog.format_wall_size(120, 96, "m") == "3.05 × 2.44 m"
    assert catalog.format_wall_size(120, 96, "furlong") == "120 × 96 in"  # unknown → inches


def test_outer_size_and_min_bottom_rules():
    assert catalog.outer_size(12, 16, 1.0, 2, 2, 2, 2) == (18, 22)
    assert catalog.outer_size(36, 24, 1.125) == (38.25, 26.25)
    assert RULES.min_bottom(False) == 12
    assert RULES.min_bottom(True) == pytest.approx(14.5689 + 8, abs=1e-3)


# ============================ Designs: validation rules ===========================


async def _design(client, headers, **wall) -> str:
    resp = await client.post(
        "/api/v1/designs",
        headers=headers,
        json={"title": "Phase 3 Wall", "wall": {"width_inches": 120, "height_inches": 96, **wall}},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _item(item_id="f1", x=6.0, y=6.0, **extra) -> dict:
    item = {
        "item_id": item_id,
        "size_id": "12x16",
        "finish_id": "natural-oak",
        "orientation": "portrait",
        "position_x_inches": x,
        "position_y_inches": y,
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
    item.update(extra)
    return item


async def _save(client, headers, design_id, items, **extra):
    return await client.post(
        f"/api/v1/designs/{design_id}/versions",
        headers=headers,
        json={"layout_type": "grid", "items": items, **extra},
    )


@pytest.fixture
async def auth(client: AsyncClient):
    user, token = await register_test_user(client, email="phase3@example.com")
    return user, {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    ("width", "height", "ok"),
    [
        (35.9, 96, False),
        (36, 96, True),
        (480, 96, True),
        (480.5, 96, False),
        (120, 47.9, False),
        (120, 48, True),
        (120, 240, True),
        (120, 240.5, False),
    ],
)
async def test_wall_limits_match_planner(client, auth, width, height, ok):
    _, headers = auth
    resp = await client.post(
        "/api/v1/designs",
        headers=headers,
        json={"title": "Bounds", "wall": {"width_inches": width, "height_inches": height}},
    )
    assert resp.status_code == (201 if ok else 422), resp.text


async def test_wall_paint_id_and_metre_unit(client, auth):
    _, headers = auth
    resp = await client.post(
        "/api/v1/designs",
        headers=headers,
        json={
            "title": "Paint",
            "wall": {
                "width_inches": 144,
                "height_inches": 108,
                "paint_id": "sand",
                "color_hex": "#000000",
                "display_unit": "m",
            },
        },
    )
    assert resp.status_code == 201, resp.text
    wall = resp.json()["wall"]
    assert (wall["paint_id"], wall["color_hex"], wall["display_unit"]) == ("sand", "#E4CFB4", "m")

    bad = await client.post(
        "/api/v1/designs",
        headers=headers,
        json={
            "title": "Paint",
            "wall": {"width_inches": 144, "height_inches": 108, "paint_id": "neon-glow"},
        },
    )
    assert bad.status_code == 422
    assert "neon-glow" not in bad.text  # error never echoes the submitted value
    detail = bad.json()["error"]["details"][0]
    assert detail["issue"].startswith("Unknown paint shade")
    assert detail["field"] == "wall.paint_id"  # full request path, not just "paint_id"


async def test_catalog_item_outer_size_is_computed_by_server(client, auth, fake_design_repo):
    _, headers = auth
    design_id = await _design(client, headers)
    resp = await _save(client, headers, design_id, [_item()])
    assert resp.status_code == 201, resp.text
    detail = (await client.get(f"/api/v1/designs/{design_id}", headers=headers)).json()
    item = detail["current_version"]["items"][0]
    # 12 x 16 + 2 x (2 in mount + 1 in natural-oak face) = 18 x 22 (frontend frameGeometry)
    assert (item["total_width_inches"], item["total_height_inches"]) == (18, 22)
    assert item["matting"]["color_id"] == "museum-white"
    assert item["matting"]["color_hex"] == "#F4F3F3"
    assert item["frame_id"] == "12x16"  # defaults to the size when omitted


async def test_item_catalog_references_are_enforced(client, auth):
    _, headers = auth
    design_id = await _design(client, headers)
    cases = {
        "unknown finish": _item(finish_id="bogus-finish"),
        "unknown size": _item(size_id="10x12"),
        "unknown mount": _item(matting={"color_id": "teal"}),
        "size/orientation mismatch": _item(orientation="landscape"),
        "square catalog size": _item(orientation="square"),
        "wrong outer size": _item(total_width_inches=16),
        "mat over 6 in": _item(matting={"top_inches": 6.5}),
        "photo and sample": _item(photo_id="a" * 24, sample_id="frame-01"),
        "bad item id": _item(item_id="../x"),
    }
    expected_field = {
        "unknown finish": "items.0.finish_id",
        "unknown mount": "items.0.matting.color_id",
        "size/orientation mismatch": "items.0",  # model-level check: the item itself
        "wrong outer size": "items.f1.total_width_inches",
    }
    for name, item in cases.items():
        resp = await _save(client, headers, design_id, [item])
        assert resp.status_code == 422, f"{name}: {resp.status_code} {resp.text}"
        assert "bogus-finish" not in resp.text
        if name in expected_field:
            assert resp.json()["error"]["details"][0]["field"] == expected_field[name], name

    ok = await _save(
        client,
        headers,
        design_id,
        [_item(matting={"top_inches": 6, "bottom_inches": 6, "left_inches": 6, "right_inches": 6})],
    )
    assert ok.status_code == 201, ok.text


async def test_version_frame_count_and_unique_ids(client, auth):
    _, headers = auth
    design_id = await _design(client, headers, width_inches=480, height_inches=240)
    sixteen = [_item(f"f{i}", x=6 + (i % 4) * 20, y=6 + (i // 4) * 24) for i in range(16)]
    assert (await _save(client, headers, design_id, sixteen)).status_code == 201
    seventeen = [*sixteen, _item("f16", x=100, y=6)]
    assert (await _save(client, headers, design_id, seventeen)).status_code == 422
    dupes = [_item("f1"), _item("f1", x=40)]
    assert (await _save(client, headers, design_id, dupes)).status_code == 422


async def test_fit_rules_match_frontend(client, auth):
    """Wall 120 x 96: margin 6 in, lowest point 12 in above the floor (bottom edge ≤ 84)."""
    _, headers = auth
    design_id = await _design(client, headers)
    # Exactly on the margin with 2-dp rounding noise passes; a real overshoot does not.
    assert (await _save(client, headers, design_id, [_item(x=5.995)])).status_code == 201
    assert (await _save(client, headers, design_id, [_item(x=5.9)])).status_code == 422
    # Bottom at 84 (12 in above the floor) passes. The old rule (24 in) rejected this.
    assert (await _save(client, headers, design_id, [_item(y=62)])).status_code == 201
    assert (await _save(client, headers, design_id, [_item(y=62.5)])).status_code == 422
    # With the sofa shown, the bottom must stay above sofa top + 8 in (≈ 22.57 in).
    sofa = {"preview": {"sofa": True}}
    assert (await _save(client, headers, design_id, [_item(y=62)], **sofa)).status_code == 422
    assert (await _save(client, headers, design_id, [_item(y=51)], **sofa)).status_code == 201
    overlap = [_item("a", x=10), _item("b", x=20)]
    assert (await _save(client, headers, design_id, overlap)).status_code == 422


async def test_version_metadata_is_typed(client, auth):
    _, headers = auth
    design_id = await _design(client, headers)
    meta = {"style": "focal_center", "gap_inches": 3, "gap_unit": "cm", "seed": 42, "variant": 2}
    resp = await _save(
        client,
        headers,
        design_id,
        [_item()],
        layout_type="focal_center",
        layout_metadata=meta,
        preview={"sofa": False, "guides": True},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["layout_type"] == "centre"
    version = (await client.get(f"/api/v1/designs/{design_id}", headers=headers)).json()[
        "current_version"
    ]
    assert version["layout_metadata"] == {**meta, "style": "centre"}
    assert version["preview"] == {"sofa": False, "guides": True}

    for bad in (
        {"layout_metadata": {"blob": "x" * 10}},
        {"layout_metadata": {"variant": 3}},
        {"layout_metadata": {"gap_inches": 13}},
        {"preview": {"sofa": True, "script": "<x>"}},
        {"layout_type": "staircase"},
        {"template_id": "../../etc"},
    ):
        assert (await _save(client, headers, design_id, [_item()], **bad)).status_code == 422, bad


async def test_changed_mount_creates_a_new_version(client, auth):
    """Any stored change (here only the mount colour) must not be swallowed as a duplicate."""
    _, headers = auth
    design_id = await _design(client, headers)
    v1 = (await _save(client, headers, design_id, [_item()])).json()
    same = (await _save(client, headers, design_id, [_item()])).json()
    assert same["version_number"] == v1["version_number"]
    changed = await _save(client, headers, design_id, [_item(matting={"color_id": "black"})])
    assert changed.json()["version_number"] == v1["version_number"] + 1


@pytest.mark.parametrize(
    ("sort", "status"),
    [
        ("updated_at:desc", 200),
        ("title:asc", 200),
        ("created_at:asc", 200),
        ("password_hash:asc", 422),  # arbitrary document fields
        ("$natural:asc", 422),  # operator-like names reached MongoDB before
        ("title", 422),
    ],
)
async def test_design_list_sort_is_allowlisted(client, auth, sort, status):
    _, headers = auth
    resp = await client.get("/api/v1/designs", headers=headers, params={"sort": sort})
    assert resp.status_code == status, resp.text


async def test_legacy_designs_still_load(client, auth, fake_design_repo: FakeDesignRepository):
    """Designs saved under the old rules (24 in wall, mm, 8 in mat, 20 frames, free-form
    metadata, SAF ids) are returned unchanged rather than failing response validation."""
    user, headers = auth
    design = DesignInDB(
        user_id=user["id"],
        title="Legacy wall",
        wall=DesignWallInDB(width_inches=24, height_inches=30, display_unit="mm"),
        current_version_number=1,
        version_counter=1,
    )
    items = [
        DesignItemInDB(
            item_id=f"legacy-{i}",
            frame_id="frame-black-12x16",
            position_x_inches=i,
            position_y_inches=0,
            photo_width_inches=12,
            photo_height_inches=16,
            total_width_inches=28,
            total_height_inches=32,
            finish_id="matte-black",
            size_id="10x12",
            matting=MattingInDB(top_inches=8, bottom_inches=8, left_inches=8, right_inches=8),
        )
        for i in range(20)
    ]
    version = DesignVersionInDB(
        design_id=design.id,
        version_number=1,
        layout_type="focal_center",
        items=items,
        bounding_box=BoundingBoxInDB(x=0, y=0, width=47, height=32),
        layout_metadata={"engine": "saf", "gap_inches": 99},
        preview={"anything": True},
    )
    design.current_version_id = version.id
    await fake_design_repo.create_design(design)
    await fake_design_repo.create_version(version)

    detail = await client.get(f"/api/v1/designs/{design.id}", headers=headers)
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["wall"]["width_inches"] == 24 and body["wall"]["display_unit"] == "mm"
    assert body["current_version"]["items_count"] == 20
    assert body["current_version"]["items"][0]["matting"]["top_inches"] == 8
    assert body["current_version"]["layout_metadata"] == {"engine": "saf", "gap_inches": 99}
    listing = await client.get("/api/v1/designs", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["items"][0]["items_count"] == 20


# ============================== Quotes: catalog-driven ============================


def _frame(i: int, size_id: str, orientation="portrait", finish="natural-oak", **mount) -> dict:
    return {
        "id": f"f{i}",
        "sizeId": size_id,
        "orientation": orientation,
        "finishId": finish,
        "mount": {"enabled": True, "colourId": "museum-white", "marginIn": 2, **mount},
        "photo": {"kind": "sample", "sampleId": f"frame-{i:02d}"},
    }


def _planner_state(frames: list[dict], **extra) -> dict:
    """The planner's own state shape (frontend PlannerState)."""
    return {
        "title": "Living   Room  Wall",
        "templateId": "balanced-grid",
        "wall": {"widthIn": 120, "heightIn": 96, "paintId": "warm-cream"},
        "displayUnit": "ft",
        "layout": {"style": "grid", "gapIn": 3, "gapUnit": "in", "seed": 0, "variant": 0},
        "frames": frames,
        "selectedIndex": 0,
        "fillWithSamples": False,
        "preview": {"sofa": True, "indexBadges": True, "guides": True},
        **extra,
    }


async def _prepare(client, headers, state, fmt="PNG", mime="image/png"):
    return await client.post(
        "/api/v1/quotes/prepare",
        headers=headers,
        data={"design_data": json.dumps(state)},
        files={"file": (f"p.{fmt.lower()}", make_test_image(800, 600, fmt=fmt), mime)},
    )


async def test_quote_dimensions_for_every_catalog_size(client, auth, fake_quote_repo):
    _, headers = auth
    frames = [
        _frame(i, s.id, "landscape" if i % 2 else "portrait", "golden-teak")
        for i, s in enumerate(catalog.FRAME_SIZES)
    ]
    frames.append(_frame(8, "12x16", enabled=False))  # no mount: outer = opening + moulding only
    resp = await _prepare(client, headers, _planner_state(frames))
    assert resp.status_code == 201, resp.text
    quote = await fake_quote_repo.get_by_reference(resp.json()["quote_id"])
    for snap, size in zip(quote.frames[:8], catalog.FRAME_SIZES, strict=True):
        w, h = size.oriented(snap.orientation)
        assert (snap.opening_width_inches, snap.opening_height_inches) == (w, h)
        assert (snap.width_inches, snap.height_inches) == (w + 2 * 3.125, h + 2 * 3.125)
        assert snap.profile_inches == 1.125
        assert snap.finish_name == "Golden Teak"
        assert (snap.mount_color_id, snap.mount_color_name) == ("museum-white", "Museum White")
    no_mount = quote.frames[8]
    assert (no_mount.width_inches, no_mount.height_inches) == (14, 18)
    # Planner state: top-level unit and sofa, paint resolved from the catalog, title cleaned
    assert quote.wall.display_unit == "ft" and quote.wall.has_sofa is True
    assert (quote.wall.paint_id, quote.wall.color_hex) == ("warm-cream", "#EFDECA")
    assert quote.design_title == "Living Room Wall"
    text = urllib.parse.unquote(resp.json()["whatsapp_url"].split("?text=")[1])
    assert "Wall Size: 10 × 8 ft\n" in text  # 120 x 96 in, shown in the customer's unit


async def test_quote_rejects_unknown_ids_instead_of_guessing(client, auth):
    _, headers = auth
    cases = {
        "size": _frame(0, "10x12"),  # SAF size; used to fall back silently to 12 x 16
        "finish": _frame(0, "12x16", finish="dark-walnut"),
        "mount": _frame(0, "12x16", colourId="teal"),
        "mat": _frame(0, "12x16", marginIn=7),
    }
    for name, frame in cases.items():
        resp = await _prepare(client, headers, _planner_state([frame]))
        assert resp.status_code == 422, f"{name}: {resp.text}"
        assert resp.json()["error"]["details"][0]["field"].startswith("design_data.frames.0")
    too_many = [_frame(i, "5x7") for i in range(17)]
    assert (await _prepare(client, headers, _planner_state(too_many))).status_code == 422
    small_wall = _planner_state([_frame(0, "5x7")], wall={"widthIn": 30, "heightIn": 96})
    assert (await _prepare(client, headers, small_wall)).status_code == 422
    bad_paint = _planner_state(
        [_frame(0, "5x7")], wall={"widthIn": 120, "heightIn": 96, "paintId": "warm-chalk"}
    )
    assert (await _prepare(client, headers, bad_paint)).status_code == 422


@pytest.mark.parametrize(
    ("fmt", "mime", "ext"),
    [("PNG", "image/png", "png"), ("JPEG", "image/jpeg", "jpg"), ("WEBP", "image/webp", "webp")],
)
async def test_quote_preview_keeps_its_format(
    client, auth, fake_quote_repo, fake_r2_storage: FakeR2Storage, fmt, mime, ext
):
    _, headers = auth
    resp = await _prepare(client, headers, _planner_state([_frame(0, "12x16")]), fmt, mime)
    assert resp.status_code == 201, resp.text
    quote = await fake_quote_repo.get_by_reference(resp.json()["quote_id"])
    assert quote.preview_image_key.endswith(f"/preview.{ext}")
    assert fake_r2_storage.objects[quote.preview_image_key][1] == mime
    token = resp.json()["report_url"].split("/q/")[1]
    preview = await client.get(f"/api/v1/quotes/share/{token}/preview")
    assert preview.headers["content-type"] == mime
    assert preview.headers["content-disposition"].endswith(f'.{ext}"')


async def test_owner_quote_detail_has_no_broken_report_link(client, auth):
    _, headers = auth
    prepared = (await _prepare(client, headers, _planner_state([_frame(0, "12x16")]))).json()
    detail = await client.get(f"/api/v1/quotes/{prepared['quote_id']}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["report_url"] is None  # was /q/<8-char prefix>, which never resolved
    assert body["wall_size"] == "10 × 8 ft"
    assert body["frames"][0]["mount"] == "Museum White (2 in border)"


async def test_legacy_quote_report_still_renders(client, fake_quote_repo: FakeQuoteRepository):
    """Quotes stored before Phase 3 (SAF finish IDs, unknown size, mount ID as name)."""
    raw = "legacy-share-token-0123456789abcdef"
    quote = QuoteInDB(
        quote_reference="MQ-2026-0900",
        user_id="a" * 24,
        customer=QuoteContactSnapshot(full_name="Old Customer", email="old@example.com"),
        layout_style="focal_center",
        wall=QuoteWallSnapshot(width_inches=120, height_inches=96, display_unit="in"),
        frames=[
            QuoteFrameSnapshot(
                item_id="f1",
                frame_number=1,
                size_id="10x12",
                orientation="landscape",
                finish_id="dark-walnut",
                finish_name="Dark Walnut",
                width_inches=16,
                height_inches=14,
                mount_enabled=True,
                mount_color_name="museum-white",
                mount_margin_inches=2,
            )
        ],
        preview_image_key="quotes/legacy/preview.png",
        share_token_hash=hash_token(raw),
        share_token_prefix=raw[:8],
        expires_at=datetime.now(UTC) + timedelta(days=5),
    )
    await fake_quote_repo.create(quote)

    html = (await client.get(f"/api/v1/quotes/share/{raw}")).text
    assert "Dark Walnut" in html
    assert "12 × 10 in" in html  # opening as hung (landscape)
    assert "Museum White (2 in border)" in html
    assert "Centre Focus" in html  # legacy layout name normalised
    data = (
        await client.get(f"/api/v1/quotes/share/{raw}", headers={"Accept": "application/json"})
    ).json()
    assert data["wall_dimensions"] == "120 × 96 in"
    assert data["frames"][0]["finish"] == "Dark Walnut"


# ===================================== Geometry ===================================


async def test_generate_layout_accepts_catalog_frames_and_zero_gap(client: AsyncClient):
    payload = {
        "wall": {"width_inches": 120, "height_inches": 96},
        "frames": [
            {"item_id": "a", "size_id": "12x16", "orientation": "landscape", "finish_id": "ivory"},
            {"item_id": "b", "size_id": "8x10", "finish_id": "walnut"},
        ],
        "layout_style": "row",
        "spacing_inches": 0,
        "seed": 1,
    }
    resp = await client.post("/api/v1/geometry/generate-layout", json=payload)
    assert resp.status_code == 200, resp.text
    items = {i["item_id"]: i for i in resp.json()["items"]}
    assert (items["a"]["photo_width_inches"], items["a"]["photo_height_inches"]) == (16, 12)
    # 16 x 12 + 2 x (2 in default mount + 0.875 in ivory face)
    assert items["a"]["outer_width_inches"] == pytest.approx(21.75)

    payload["frames"][0]["photo_width_inches"] = 12  # contradicts size + orientation
    assert (await client.post("/api/v1/geometry/generate-layout", json=payload)).status_code == 422
    payload["frames"] = [{"item_id": f"f{i}"} for i in range(17)]
    assert (await client.post("/api/v1/geometry/generate-layout", json=payload)).status_code == 422


async def test_validate_layout_uses_planner_minimum_bottom(client: AsyncClient):
    body = {
        "wall": {"width_inches": 120, "height_inches": 96},
        "frames": [
            {
                "item_id": "a",
                "outer_x_inches": 50,
                "outer_y_inches": 64,
                "outer_width_inches": 20,
                "outer_height_inches": 20,
            }
        ],
    }
    ok = (await client.post("/api/v1/geometry/validate-layout", json=body)).json()
    assert ok["is_valid"] is True  # bottom 84 = 12 in above the floor
    body["wall"]["has_sofa"] = True
    sofa = (await client.post("/api/v1/geometry/validate-layout", json=body)).json()
    assert sofa["is_valid"] is False
    assert (
        await client.post(
            "/api/v1/geometry/validate-layout",
            json={**body, "wall": {"width_inches": 30, "height_inches": 96}},
        )
    ).status_code == 422


# ===================================== Branding ===================================


def test_password_reset_email_is_moonlight_branded_and_self_contained():
    html = render_otp_email_html("482913", expiry_minutes=10)
    assert "482913" in html and "10 minutes" in html
    assert "#9B1118" in html and "#FDF6EC" in html  # crimson on cream
    assert "#0F0F11" not in html  # old dark SAF palette
    assert "http" not in html  # no remote fonts, images or links


def test_debug_logging_never_enables_pymongo_command_documents():
    """LOG_LEVEL=DEBUG must not make PyMongo log whole documents (password hashes, contacts)."""
    import logging

    from app.core.logging import setup_logging

    root = logging.getLogger()
    saved_handlers, saved_level = list(root.handlers), root.level
    try:
        setup_logging("DEBUG")
        assert logging.getLogger("pymongo.command").getEffectiveLevel() >= logging.INFO
        assert logging.getLogger("app").getEffectiveLevel() == logging.DEBUG
    finally:
        for handler in list(root.handlers):
            root.removeHandler(handler)
        for handler in saved_handlers:
            root.addHandler(handler)
        root.setLevel(saved_level)
