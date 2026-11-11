from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    AccountDisabledException,
    InvalidTokenException,
    TokenExpiredException,
    TokenRevokedException,
)
from app.core.security import decode_access_token
from app.db.dependencies import get_db
from app.integrations.groq_client import GroqClient
from app.models.user import UserInDB
from app.repositories.ai_cache_repository import AICacheRepository
from app.repositories.catalog_repository import CatalogRepository
from app.repositories.design_repository import DesignRepository
from app.repositories.photo_repository import PhotoRepository
from app.repositories.quote_repository import QuoteRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.template_repository import TemplateRepository
from app.repositories.user_repository import UserRepository
from app.services.ai_usage_service import AIUsageService
from app.services.auth_service import AuthService
from app.services.catalog_service import CatalogService
from app.services.design_service import DesignService
from app.services.google_auth_service import GoogleAuthService
from app.services.image_processing_service import ImageProcessingService
from app.services.layout_service import LayoutService
from app.services.photo_analysis_service import PhotoAnalysisService
from app.services.photo_service import PhotoService
from app.services.quote_report_service import QuoteReportService
from app.services.quote_service import QuoteService
from app.services.redesign_service import RedesignService
from app.services.template_service import TemplateService
from app.services.token_service import TokenService
from app.services.whatsapp_service import WhatsAppService
from app.storage.r2_storage import R2Storage

# Bearer token extractor
_bearer_security = HTTPBearer(auto_error=False)


async def get_user_repository(db: Annotated[AsyncDatabase, Depends(get_db)]) -> UserRepository:
    """Dependency for UserRepository."""
    return UserRepository(db)


async def get_session_repository(
    db: Annotated[AsyncDatabase, Depends(get_db)],
) -> SessionRepository:
    """Dependency for SessionRepository."""
    return SessionRepository(db)


async def get_token_service(
    session_repo: Annotated[SessionRepository, Depends(get_session_repository)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> TokenService:
    """Dependency for TokenService."""
    return TokenService(session_repo=session_repo, user_repo=user_repo)


async def get_auth_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    session_repo: Annotated[SessionRepository, Depends(get_session_repository)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
) -> AuthService:
    """Dependency for AuthService."""
    return AuthService(
        user_repo=user_repo,
        session_repo=session_repo,
        token_service=token_service,
    )


async def get_google_auth_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
) -> GoogleAuthService:
    """Dependency for GoogleAuthService."""
    return GoogleAuthService(user_repo=user_repo, token_service=token_service)


async def get_current_user(
    auth: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_security)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserInDB:
    """Verify Bearer token and return active authenticated user."""
    if not auth or not auth.credentials:
        raise InvalidTokenException("Missing Bearer authorization header.")

    try:
        payload = decode_access_token(auth.credentials)
    except Exception as exc:
        err_msg = str(exc).lower()
        if "expired" in err_msg:
            raise TokenExpiredException() from exc
        raise InvalidTokenException() from exc

    user_id = payload.get("sub")
    if not user_id:
        raise InvalidTokenException("Token payload missing subject.")

    user = await user_repo.get_by_id(user_id)
    if not user:
        raise InvalidTokenException("User associated with token no longer exists.")

    if not user.is_active:
        raise AccountDisabledException()

    if user.password_changed_at:
        token_iat = datetime.fromtimestamp(payload.get("iat", 0), tz=UTC)
        pwd_changed = (
            user.password_changed_at.replace(tzinfo=UTC)
            if user.password_changed_at.tzinfo is None
            else user.password_changed_at
        )
        if token_iat < pwd_changed:
            raise TokenRevokedException("Access token invalidated due to password change.")

    return user


async def get_current_active_user(
    current_user: Annotated[UserInDB, Depends(get_current_user)],
) -> UserInDB:
    """Assert authenticated user is active."""
    return current_user


async def get_catalog_repository(
    db: Annotated[AsyncDatabase, Depends(get_db)],
) -> CatalogRepository:
    """Dependency for CatalogRepository."""
    return CatalogRepository(db)


async def get_template_repository(
    db: Annotated[AsyncDatabase, Depends(get_db)],
) -> TemplateRepository:
    """Dependency for TemplateRepository."""
    return TemplateRepository(db)


async def get_catalog_service(
    catalog_repo: Annotated[CatalogRepository, Depends(get_catalog_repository)],
) -> CatalogService:
    """Dependency for CatalogService."""
    return CatalogService(catalog_repo=catalog_repo)


async def get_template_service(
    template_repo: Annotated[TemplateRepository, Depends(get_template_repository)],
) -> TemplateService:
    """Dependency for TemplateService."""
    return TemplateService(template_repo=template_repo)


async def get_optional_current_user(
    auth: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_security)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserInDB | None:
    """Extract authenticated user if Bearer token present, else return None without error."""
    if not auth or not auth.credentials:
        return None
    try:
        payload = decode_access_token(auth.credentials)
        user_id = payload.get("sub")
        if user_id:
            user = await user_repo.get_by_id(user_id)
            if user and user.is_active:
                return user
    except Exception:
        return None
    return None


async def get_photo_repository(
    db: Annotated[AsyncDatabase, Depends(get_db)],
) -> PhotoRepository:
    """Dependency for PhotoRepository."""
    return PhotoRepository(db)


async def get_image_processing_service() -> ImageProcessingService:
    """Dependency for ImageProcessingService."""
    return ImageProcessingService()


async def get_r2_storage() -> R2Storage:
    """Dependency for Cloudflare R2 storage client."""
    return R2Storage()


async def get_photo_service(
    photo_repo: Annotated[PhotoRepository, Depends(get_photo_repository)],
    image_service: Annotated[ImageProcessingService, Depends(get_image_processing_service)],
    r2_storage: Annotated[R2Storage, Depends(get_r2_storage)],
) -> PhotoService:
    """Dependency for PhotoService."""
    return PhotoService(
        photo_repo=photo_repo,
        image_service=image_service,
        r2_storage=r2_storage,
    )


async def get_photo_analysis_service(
    photo_repo: Annotated[PhotoRepository, Depends(get_photo_repository)],
    r2_storage: Annotated[R2Storage, Depends(get_r2_storage)],
) -> PhotoAnalysisService:
    """Dependency for PhotoAnalysisService."""
    return PhotoAnalysisService(photo_repo=photo_repo, r2_storage=r2_storage)


# Global singletons for AI usage budgeting and response caching
_ai_cache_repo_instance = AICacheRepository()
_ai_usage_service_instance: AIUsageService | None = None


def get_ai_cache_repository() -> AICacheRepository:
    return _ai_cache_repo_instance


def get_ai_usage_service(settings: Annotated[Settings, Depends(get_settings)]) -> AIUsageService:
    global _ai_usage_service_instance
    if _ai_usage_service_instance is None:
        _ai_usage_service_instance = AIUsageService(settings=settings)
    return _ai_usage_service_instance


async def get_groq_client(settings: Annotated[Settings, Depends(get_settings)]) -> GroqClient:
    """Dependency for GroqClient."""
    return GroqClient(settings=settings)


async def get_layout_service(
    photo_repo: Annotated[PhotoRepository, Depends(get_photo_repository)],
    photo_analysis_service: Annotated[PhotoAnalysisService, Depends(get_photo_analysis_service)],
    groq_client: Annotated[GroqClient, Depends(get_groq_client)],
    ai_usage_service: Annotated[AIUsageService, Depends(get_ai_usage_service)],
    ai_cache_repo: Annotated[AICacheRepository, Depends(get_ai_cache_repository)],
) -> LayoutService:
    """Dependency for LayoutService."""
    return LayoutService(
        photo_repo=photo_repo,
        photo_analysis_service=photo_analysis_service,
        groq_client=groq_client,
        ai_usage_service=ai_usage_service,
        ai_cache_repo=ai_cache_repo,
    )


async def get_redesign_service(
    photo_repo: Annotated[PhotoRepository, Depends(get_photo_repository)],
    photo_analysis_service: Annotated[PhotoAnalysisService, Depends(get_photo_analysis_service)],
    groq_client: Annotated[GroqClient, Depends(get_groq_client)],
    ai_usage_service: Annotated[AIUsageService, Depends(get_ai_usage_service)],
    ai_cache_repo: Annotated[AICacheRepository, Depends(get_ai_cache_repository)],
) -> RedesignService:
    """Dependency for RedesignService."""
    return RedesignService(
        photo_repo=photo_repo,
        photo_analysis_service=photo_analysis_service,
        groq_client=groq_client,
        ai_usage_service=ai_usage_service,
        ai_cache_repo=ai_cache_repo,
    )


async def get_design_repository(
    db: Annotated[AsyncDatabase, Depends(get_db)],
) -> DesignRepository:
    """Dependency for DesignRepository."""
    return DesignRepository(db)


async def get_design_service(
    design_repo: Annotated[DesignRepository, Depends(get_design_repository)],
    photo_repo: Annotated[PhotoRepository, Depends(get_photo_repository)],
) -> DesignService:
    """Dependency for DesignService."""
    return DesignService(design_repo=design_repo, photo_repo=photo_repo)


async def get_quote_repository(
    db: Annotated[AsyncDatabase, Depends(get_db)],
) -> QuoteRepository:
    """Dependency for QuoteRepository."""
    return QuoteRepository(db)


async def get_whatsapp_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> WhatsAppService:
    """Dependency for WhatsAppService."""
    return WhatsAppService(business_number=settings.BUSINESS_WHATSAPP_NUMBER)


async def get_quote_report_service() -> QuoteReportService:
    """Dependency for QuoteReportService."""
    return QuoteReportService()


async def get_quote_service(
    quote_repo: Annotated[QuoteRepository, Depends(get_quote_repository)],
    photo_repo: Annotated[PhotoRepository, Depends(get_photo_repository)],
    r2_storage: Annotated[R2Storage, Depends(get_r2_storage)],
    whatsapp_service: Annotated[WhatsAppService, Depends(get_whatsapp_service)],
    report_service: Annotated[QuoteReportService, Depends(get_quote_report_service)],
) -> QuoteService:
    """Dependency for QuoteService."""
    return QuoteService(
        quote_repo=quote_repo,
        photo_repo=photo_repo,
        r2_storage=r2_storage,
        whatsapp_service=whatsapp_service,
        report_service=report_service,
    )


# Type aliases for clean endpoint injections
SettingsDep = Annotated[Settings, Depends(get_settings)]
DatabaseDep = Annotated[AsyncDatabase, Depends(get_db)]
UserRepoDep = Annotated[UserRepository, Depends(get_user_repository)]
SessionRepoDep = Annotated[SessionRepository, Depends(get_session_repository)]
CatalogRepoDep = Annotated[CatalogRepository, Depends(get_catalog_repository)]
TemplateRepoDep = Annotated[TemplateRepository, Depends(get_template_repository)]
PhotoRepoDep = Annotated[PhotoRepository, Depends(get_photo_repository)]
QuoteRepoDep = Annotated[QuoteRepository, Depends(get_quote_repository)]
ImageProcessingServiceDep = Annotated[ImageProcessingService, Depends(get_image_processing_service)]
R2StorageDep = Annotated[R2Storage, Depends(get_r2_storage)]
PhotoServiceDep = Annotated[PhotoService, Depends(get_photo_service)]
PhotoAnalysisServiceDep = Annotated[PhotoAnalysisService, Depends(get_photo_analysis_service)]
GroqClientDep = Annotated[GroqClient, Depends(get_groq_client)]
LayoutServiceDep = Annotated[LayoutService, Depends(get_layout_service)]
RedesignServiceDep = Annotated[RedesignService, Depends(get_redesign_service)]
TokenServiceDep = Annotated[TokenService, Depends(get_token_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
GoogleAuthServiceDep = Annotated[GoogleAuthService, Depends(get_google_auth_service)]
CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]
TemplateServiceDep = Annotated[TemplateService, Depends(get_template_service)]
DesignRepoDep = Annotated[DesignRepository, Depends(get_design_repository)]
DesignServiceDep = Annotated[DesignService, Depends(get_design_service)]
WhatsAppServiceDep = Annotated[WhatsAppService, Depends(get_whatsapp_service)]
QuoteReportServiceDep = Annotated[QuoteReportService, Depends(get_quote_report_service)]
QuoteServiceDep = Annotated[QuoteService, Depends(get_quote_service)]
CurrentUserDep = Annotated[UserInDB, Depends(get_current_user)]
OptionalCurrentUserDep = Annotated[UserInDB | None, Depends(get_optional_current_user)]
