import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_v1_router
from app.core.config import Settings, get_settings
from app.core.handlers import register_exception_handlers
from app.core.logging import setup_logging
from app.db.mongodb import mongo_manager
from app.repositories.catalog_repository import CatalogRepository
from app.repositories.design_repository import DesignRepository
from app.repositories.photo_repository import PhotoRepository
from app.repositories.quote_repository import QuoteRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.template_repository import TemplateRepository
from app.repositories.user_repository import UserRepository

logger = logging.getLogger("saf_studio.app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context managing startup and shutdown tasks."""
    override = app.dependency_overrides.get(get_settings)
    settings: Settings = override() if override else get_settings()

    # 1. Setup structured logging
    setup_logging(
        log_level=settings.LOG_LEVEL,
        json_logs=settings.is_production,
    )
    logger.info(
        "Starting %s v%s in %s mode",
        settings.APP_NAME,
        settings.VERSION,
        settings.ENVIRONMENT,
    )

    # 2. Initialize asynchronous MongoDB connection pool and indexes
    if settings.ENVIRONMENT != "test":
        try:
            await mongo_manager.connect(settings)
            user_repo = UserRepository(mongo_manager.get_database())
            session_repo = SessionRepository(mongo_manager.get_database())
            catalog_repo = CatalogRepository(mongo_manager.get_database())
            template_repo = TemplateRepository(mongo_manager.get_database())
            photo_repo = PhotoRepository(mongo_manager.get_database())
            design_repo = DesignRepository(mongo_manager.get_database())
            quote_repo = QuoteRepository(mongo_manager.get_database())
            await user_repo.create_indexes()
            await session_repo.create_indexes()
            await catalog_repo.create_indexes()
            await template_repo.create_indexes()
            await photo_repo.create_indexes()
            await design_repo.create_indexes()
            await quote_repo.create_indexes()
            logger.info("MongoDB collection indexes verified")
        except Exception as exc:
            logger.warning(
                "MongoDB initial connection deferred or failed: %s (will retry on readiness check)",
                exc,
            )

    yield

    # 3. Shutdown: Cleanly close MongoDB connection pool
    if settings.ENVIRONMENT != "test":
        logger.info("Shutting down %s", settings.APP_NAME)
        await mongo_manager.disconnect()
        logger.info("Shutdown complete")


def create_application() -> FastAPI:
    """FastAPI application factory."""
    settings = get_settings()

    docs_url = "/docs" if (settings.DEBUG or not settings.is_production) else None
    redoc_url = "/redoc" if (settings.DEBUG or not settings.is_production) else None
    openapi_url = (
        f"{settings.API_V1_STR}/openapi.json"
        if (settings.DEBUG or not settings.is_production)
        else None
    )

    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.VERSION,
        description="FastAPI Backend for SAF Studio Gallery Wall Platform",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )

    # Configure CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Register global error normalization handlers
    register_exception_handlers(application)

    # Mount API v1 router
    application.include_router(api_v1_router, prefix=settings.API_V1_STR)

    @application.get("/q/{token}", include_in_schema=False)
    async def redirect_quote_report(token: str) -> JSONResponse:
        from fastapi.responses import RedirectResponse

        return RedirectResponse(
            url=f"{settings.API_V1_STR}/quotes/share/{token}",
            status_code=307,
        )

    @application.get("/", include_in_schema=False)
    async def root_info(
        current_cfg: Settings = Depends(get_settings),
    ) -> JSONResponse:
        return JSONResponse(
            content={
                "service": current_cfg.APP_NAME,
                "version": current_cfg.VERSION,
                "environment": current_cfg.ENVIRONMENT,
                "api_docs": docs_url,
                "health": f"{current_cfg.API_V1_STR}/health/live",
            }
        )

    return application


app = create_application()
