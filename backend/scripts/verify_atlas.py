"""MongoDB Atlas Connectivity, Verification, and Seeding Diagnostic Tool.

Usage:
    python backend/scripts/verify_atlas.py [--no-seed] [--overwrite-seed] [--timeout-ms 5000]

Verifies:
1. Atlas M0 connection string parsing and TLS/certifi configuration.
2. Latency and server build information.
3. Automated idempotent index creation across all domain collections.
4. Safe read/write/delete permissions.
5. Catalog and layout template seeding for fresh database initialization.
"""

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Any

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import Settings, get_settings
from app.core.logging import sanitize_sensitive_data
from app.db.mongodb import mongo_manager
from app.db.seed_catalog import seed_catalogs_and_templates
from app.repositories.catalog_repository import CatalogRepository
from app.repositories.design_repository import DesignRepository
from app.repositories.photo_repository import PhotoRepository
from app.repositories.quote_repository import QuoteRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.template_repository import TemplateRepository
from app.repositories.user_repository import UserRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("saf_studio.atlas_verifier")


def p(msg: str = "") -> None:
    """Print message with immediate flush to standard output."""
    print(msg, flush=True)


async def run_verifier(auto_seed: bool = True, overwrite_seed: bool = False, timeout_ms: int | None = None) -> bool:
    settings = get_settings()
    if timeout_ms is not None:
        settings = Settings(**{**settings.model_dump(), "MONGODB_TIMEOUT_MS": timeout_ms})

    masked_url = sanitize_sensitive_data(settings.MONGODB_URL)
    is_atlas = settings.MONGODB_URL.startswith("mongodb+srv://")

    p("\n" + "=" * 70)
    p(" SAF STUDIO — MONGODB ATLAS VERIFICATION & INITIALIZATION")
    p("=" * 70)
    p(f" Target Mode    : {'MongoDB Atlas (Cloud M0)' if is_atlas else 'Local / Self-Hosted MongoDB'}")
    p(f" Database Name  : {settings.DATABASE_NAME}")
    p(f" Masked URI     : {masked_url}")
    p(f" Timeout (ms)   : {settings.MONGODB_TIMEOUT_MS}")
    p("=" * 70 + "\n")

    # Step 1: Initialize connection
    p("[1/5] Establishing asynchronous connection pool...")
    try:
        await mongo_manager.connect(settings)
        db = mongo_manager.get_database()
        p("      ✓ Connection pool successfully established.")
    except Exception as exc:
        p(f"      ✗ Connection initialization failed: {exc}")
        p("\n[Troubleshooting Tips]:")
        if "<password>" in settings.MONGODB_URL:
            p("  - MONGODB_URL contains placeholder '<password>'. Update it with your Atlas password.")
        elif is_atlas:
            p("  - Verify MongoDB Atlas Network Access: Ensure your IP is whitelisted (or 0.0.0.0/0).")
            p("  - Verify Database User: Ensure username and password are correct and user has readWriteAnyDatabase.")
            p("  - Special Characters: URL-encode any '@', ':', or '#' characters in your password.")
        return False

    # Step 2: Measure Ping Latency and Fetch Server Info
    p("\n[2/5] Testing round-trip latency & server metadata...")
    try:
        latency = await mongo_manager.ping()
        server_info = await db.command("buildinfo")
        version = server_info.get("version", "unknown")
        git_version = server_info.get("gitVersion", "unknown")[:8]
        p(f"      ✓ Ping latency: {latency} ms")
        p(f"      ✓ MongoDB Version: {version} (build: {git_version})")
    except Exception as exc:
        p(f"      ✗ Ping failed: {exc}")
        await mongo_manager.disconnect()
        p("\n[Troubleshooting Tips]:")
        if is_atlas:
            p("  - Server ping timed out against Atlas cluster.")
            p("  - Check MongoDB Atlas Web Console -> Network Access (IP Whitelist).")
            p("  - Ensure your current IP is whitelisted or add 0.0.0.0/0.")
        else:
            p("  - Local MongoDB instance not reachable on port 27017.")
            p("  - To connect to Atlas, configure MONGODB_URL in backend/.env.")
        return False

    # Step 3: Verify and Ensure Indexes
    p("\n[3/5] Verifying collection indexes across all repositories...")
    try:
        user_repo = UserRepository(db)
        session_repo = SessionRepository(db)
        catalog_repo = CatalogRepository(db)
        template_repo = TemplateRepository(db)
        photo_repo = PhotoRepository(db)
        design_repo = DesignRepository(db)
        quote_repo = QuoteRepository(db)

        await user_repo.create_indexes()
        await session_repo.create_indexes()
        await catalog_repo.create_indexes()
        await template_repo.create_indexes()
        await photo_repo.create_indexes()
        await design_repo.create_indexes()
        await quote_repo.create_indexes()

        collections = await db.list_collection_names()
        p(f"      ✓ Idempotent indexes verified successfully on {len(collections)} collections:")
        for col_name in sorted(collections):
            idx_cursor = await db[col_name].list_indexes()
            idx_list = [idx["name"] async for idx in idx_cursor]
            p(f"        - {col_name:<20} ({len(idx_list)} indexes: {', '.join(idx_list)})")
    except Exception as exc:
        p(f"      ✗ Index initialization failed: {exc}")
        await mongo_manager.disconnect()
        return False

    # Step 4: Verify CRUD Privileges (Safe Sandbox Probe)
    p("\n[4/5] Testing read/write/delete permissions (safe probe)...")
    probe_col = db["_connectivity_probe"]
    test_doc = {"probe_id": "atlas_verifier_probe", "timestamp": time.time(), "test": True}
    try:
        # Write
        res = await probe_col.insert_one(test_doc)
        doc_id = res.inserted_id
        # Read
        found = await probe_col.find_one({"_id": doc_id})
        assert found is not None and found["probe_id"] == "atlas_verifier_probe"
        # Delete
        await probe_col.delete_one({"_id": doc_id})
        # Drop temp collection if empty
        await probe_col.drop()
        p("      ✓ Write, Read, and Delete permissions verified successfully.")
    except Exception as exc:
        p(f"      ✗ Permission verification failed: {exc}")
        await mongo_manager.disconnect()
        return False

    # Step 5: Catalog and Layout Template Seeding
    p("\n[5/5] Checking fresh database catalog & template data...")
    try:
        mat_count = await db["frame_materials"].count_documents({})
        mold_count = await db["frame_moldings"].count_documents({})
        tmpl_count = await db["layout_templates"].count_documents({})
        user_count = await db["users"].count_documents({})

        p(f"      - Users count         : {user_count} (Fresh DB confirmation: historical data NOT migrated)")
        p(f"      - Frame Materials     : {mat_count}")
        p(f"      - Frame Moldings      : {mold_count}")
        p(f"      - Layout Templates    : {tmpl_count}")

        if (mat_count == 0 or mold_count == 0 or tmpl_count == 0 or overwrite_seed) and auto_seed:
            p("      → Fresh database detected. Seeding default catalog materials, moldings, and templates...")
            seed_results = await seed_catalogs_and_templates(db, overwrite=overwrite_seed)
            p(f"      ✓ Seeding complete: {seed_results}")
        else:
            p("      ✓ Catalog and templates already seeded.")
    except Exception as exc:
        p(f"      ✗ Seeding check or execution failed: {exc}")
        await mongo_manager.disconnect()
        return False

    await mongo_manager.disconnect()
    p("\n" + "=" * 70)
    p(" ALL ATLAS CHECKS PASSED — READY FOR PRODUCTION OPERATION")
    p("=" * 70 + "\n")
    return True


async def main() -> None:
    parser = argparse.ArgumentParser(description="SAF Studio MongoDB Atlas Verifier")
    parser.add_argument("--no-seed", action="store_true", help="Do not auto-seed empty catalog collections")
    parser.add_argument("--overwrite-seed", action="store_true", help="Overwrite catalog items if they exist")
    parser.add_argument("--timeout-ms", type=int, default=None, help="Override timeout in milliseconds")
    args = parser.parse_args()

    success = await run_verifier(
        auto_seed=not args.no_seed,
        overwrite_seed=args.overwrite_seed,
        timeout_ms=args.timeout_ms,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
