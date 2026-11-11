from app.modules.geometry import (
    FrameGeometry,
    LayoutInput,
    Rect,
    Size,
    bounds,
    build_scene,
    centre_layout,
    conflicts,
    grid_layout,
    is_meaningfully_different,
    layout_similarity,
    overlaps,
    row_layout,
    salon_layout,
    suggest_layouts,
    validate_placed_frames,
)


def test_rect_bounds_and_area():
    r1 = Rect(x=10.0, y=10.0, w=20.0, h=30.0)
    r2 = Rect(x=50.0, y=20.0, w=10.0, h=10.0)
    b = bounds([r1, r2])
    assert b.x == 10.0
    assert b.y == 10.0
    assert b.w == 50.0  # 60 - 10
    assert b.h == 30.0  # 40 - 10


def test_rect_conflicts_and_overlaps():
    r1 = Rect(x=0.0, y=0.0, w=10.0, h=10.0)
    r2 = Rect(x=5.0, y=5.0, w=10.0, h=10.0)  # Intersects r1
    r3 = Rect(x=12.0, y=0.0, w=10.0, h=10.0)  # Gap of 2.0 from r1

    assert overlaps(r1, r2) is True
    assert overlaps(r1, r3) is False
    assert conflicts(r1, r3, gap=3.0) is True  # Gap of 2 is less than 3
    assert conflicts(r1, r3, gap=1.0) is False  # Gap of 2 is more than 1


def test_grid_layout_deterministic():
    sizes = [Size(12.0, 16.0) for _ in range(6)]
    inp = LayoutInput(sizes=sizes, gap=3.0, max_width=120.0, max_height=80.0, variant=0, seed=123)
    rects1 = grid_layout(inp)
    rects2 = grid_layout(inp)

    assert len(rects1) == 6
    # Exact determinism
    for r1, r2 in zip(rects1, rects2, strict=False):
        assert r1.x == r2.x
        assert r1.y == r2.y
        assert r1.w == r2.w
        assert r1.h == r2.h

    # Zero overlap
    for i in range(len(rects1)):
        for j in range(i + 1, len(rects1)):
            assert overlaps(rects1[i], rects1[j]) is False


def test_salon_layout_zero_overlap():
    sizes = [
        Size(20.0, 30.0),
        Size(12.0, 16.0),
        Size(12.0, 16.0),
        Size(8.0, 10.0),
        Size(8.0, 10.0),
    ]
    inp = LayoutInput(sizes=sizes, gap=3.0, max_width=100.0, max_height=80.0, variant=0, seed=456)
    rects = salon_layout(inp)
    assert len(rects) == 5

    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            assert overlaps(rects[i], rects[j]) is False


def test_centre_layout_anchor_and_balance():
    sizes = [
        Size(24.0, 36.0),  # Hero
        Size(12.0, 16.0),
        Size(12.0, 16.0),
        Size(12.0, 16.0),
        Size(12.0, 16.0),
    ]
    inp = LayoutInput(sizes=sizes, gap=3.0, max_width=120.0, max_height=80.0, variant=0, seed=789)
    rects = centre_layout(inp)
    assert len(rects) == 5

    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            assert overlaps(rects[i], rects[j]) is False


def test_row_layout_alignment():
    sizes = [Size(12.0, 16.0), Size(14.0, 18.0), Size(12.0, 16.0)]
    inp = LayoutInput(sizes=sizes, gap=3.0, max_width=100.0, max_height=80.0, variant=0, seed=101)
    rects = row_layout(inp)
    assert len(rects) == 3

    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            assert overlaps(rects[i], rects[j]) is False


def test_build_scene_and_eye_level():
    frames = [
        FrameGeometry(
            item_id=f"f{i}",
            opening_w=12.0,
            opening_h=16.0,
            mat_in=2.0,
            profile_in=1.0,
            outer_w=18.0,
            outer_h=22.0,
        )
        for i in range(4)
    ]
    scene = build_scene(
        wall_w=120.0,
        wall_h=96.0,
        frames=frames,
        style="grid",
        gap=3.0,
        variant=0,
        seed=1,
    )

    assert scene.fits is True
    assert len(scene.frames) == 4
    # Wall height 96, eye level 57 -> eye level y = 39
    assert scene.eye_level_y == 39.0
    # Arrangement should be centered near eye level
    arr_center_y = scene.arrangement.center_y
    assert abs(arr_center_y - scene.eye_level_y) < 15.0


def test_suggest_layouts_ranking():
    frames = [
        FrameGeometry(
            item_id=f"f{i}",
            opening_w=12.0,
            opening_h=16.0,
            mat_in=1.5,
            profile_in=1.0,
            outer_w=17.0,
            outer_h=21.0,
        )
        for i in range(4)
    ]
    suggestions = suggest_layouts(wall_w=120.0, wall_h=96.0, frames=frames, gap=3.0)
    assert len(suggestions) > 0
    # Top suggestion must fit the wall
    assert suggestions[0].scene.fits is True
    assert suggestions[0].score <= suggestions[-1].score


def test_validate_placed_frames_detects_collision():
    frames = [
        {
            "item_id": "frame-1",
            "outer_x_inches": 20.0,
            "outer_y_inches": 20.0,
            "outer_width_inches": 18.0,
            "outer_height_inches": 22.0,
        },
        {
            "item_id": "frame-2",
            "outer_x_inches": 25.0,  # Overlaps frame-1
            "outer_y_inches": 25.0,
            "outer_width_inches": 18.0,
            "outer_height_inches": 22.0,
        },
    ]
    res = validate_placed_frames(wall_w=120.0, wall_h=96.0, frames=frames)
    assert res.is_valid is False
    assert len(res.errors) >= 1
    assert res.errors[0].code == "GEOMETRY_COLLISION_DETECTED"
    assert "frame-1" in res.errors[0].item_ids
    assert "frame-2" in res.errors[0].item_ids


def test_layout_similarity_and_difference():
    r1 = [Rect(0, 0, 10, 10), Rect(15, 0, 10, 10)]
    r2 = [Rect(0, 0, 10, 10), Rect(15, 0, 10, 10)]  # Identical
    r3 = [Rect(0, 0, 10, 10), Rect(0, 15, 10, 10)]  # Vertical column

    assert layout_similarity(r1, r2) > 0.99
    assert is_meaningfully_different(r1, r3) is True
