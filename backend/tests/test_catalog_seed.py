import pytest

from app.db.seed_catalog import (
    FRONTEND_WOOD_FINISHES,
    SEED_MATERIALS,
    SEED_MOLDINGS,
    SEED_TEMPLATES,
)
from app.models.catalog import FrameMaterialInDB
from tests.fakes import FakeCatalogRepository, FakeTemplateRepository, populate_fake_catalog


def test_seed_data_counts_and_constants():
    """Verify master seed data counts and alignment with frontend specs."""
    assert len(SEED_MATERIALS) == 4
    assert len(SEED_MOLDINGS) == 4
    assert len(SEED_TEMPLATES) == 10
    assert len(FRONTEND_WOOD_FINISHES) == 8


def test_seed_frontend_wood_finishes_have_valid_swatches():
    """Verify frontend wood finish swatches contain valid hex codes and profiles."""
    for finish in FRONTEND_WOOD_FINISHES:
        assert finish["hex"].startswith("#")
        assert len(finish["hex"]) == 7
        assert finish["profile_in"] > 0
        assert len(finish["name"]) > 0


@pytest.mark.asyncio
async def test_idempotent_seeding_repeated(
    fake_catalog_repo: FakeCatalogRepository,
    fake_template_repo: FakeTemplateRepository,
):
    """Running seeding multiple times never creates duplicates."""
    # First seed
    populate_fake_catalog(fake_catalog_repo, fake_template_repo)
    initial_materials = len(fake_catalog_repo.materials)
    initial_moldings = len(fake_catalog_repo.moldings)
    initial_templates = len(fake_template_repo.templates)

    assert initial_materials == 4
    assert initial_moldings == 4
    assert initial_templates == 10

    # Second seed with same repos
    for mat_data in SEED_MATERIALS:
        mat = FrameMaterialInDB(**mat_data)
        await fake_catalog_repo.upsert_material(mat, overwrite=False)

    materials_after = await fake_catalog_repo.list_materials(available_only=False)
    assert len(materials_after) == 4


@pytest.mark.asyncio
async def test_seed_preserves_customized_data_without_overwrite(
    fake_catalog_repo: FakeCatalogRepository,
):
    """When overwrite=False, manually customized fields are preserved."""
    # Insert custom material
    mat = FrameMaterialInDB(
        code="CUSTOM-WOOD-01",
        name="Customized Wood",
        category="wood",
        finish="Custom Oil",
        base_price_per_linear_inch="99.00",
        waste_factor_percentage=20.0,
        thumbnail_url="/custom.webp",
        is_available=True,
    )
    await fake_catalog_repo.upsert_material(mat, overwrite=False)

    # Attempt to re-insert with different price but overwrite=False
    mat_duplicate = FrameMaterialInDB(
        code="CUSTOM-WOOD-01",
        name="Should Not Overwrite",
        category="wood",
        finish="New Finish",
        base_price_per_linear_inch="10.00",
        waste_factor_percentage=5.0,
        thumbnail_url="/new.webp",
        is_available=True,
    )
    result = await fake_catalog_repo.upsert_material(mat_duplicate, overwrite=False)

    assert result.name == "Customized Wood"
    assert result.base_price_per_linear_inch == "99.00"


@pytest.mark.asyncio
async def test_seed_updates_when_overwrite_true(
    fake_catalog_repo: FakeCatalogRepository,
):
    """When overwrite=True, fields are updated while preserving identifier."""
    mat = FrameMaterialInDB(
        code="UPDATE-WOOD-01",
        name="Old Name",
        category="wood",
        finish="Old Finish",
        base_price_per_linear_inch="15.00",
        waste_factor_percentage=10.0,
        thumbnail_url="/old.webp",
        is_available=True,
    )
    saved = await fake_catalog_repo.upsert_material(mat, overwrite=False)
    original_id = saved.id

    updated = FrameMaterialInDB(
        id=original_id,
        code="UPDATE-WOOD-01",
        name="Updated Name",
        category="wood",
        finish="Updated Finish",
        base_price_per_linear_inch="25.00",
        waste_factor_percentage=12.0,
        thumbnail_url="/updated.webp",
        is_available=True,
    )
    res = await fake_catalog_repo.upsert_material(updated, overwrite=True)

    assert res.name == "Updated Name"
    assert res.base_price_per_linear_inch == "25.00"
    assert str(res.id) == str(original_id)


@pytest.mark.asyncio
async def test_catalog_molding_references_valid_materials(
    fake_catalog_repo: FakeCatalogRepository,
    fake_template_repo: FakeTemplateRepository,
):
    """All seeded moldings have a material_id corresponding to an existing material."""
    populate_fake_catalog(fake_catalog_repo, fake_template_repo)
    moldings = await fake_catalog_repo.list_moldings()
    materials = await fake_catalog_repo.list_materials(available_only=False)
    material_ids = {str(m.id) for m in materials}

    assert len(moldings) >= 4
    for molding in moldings:
        assert str(molding.material_id) in material_ids
