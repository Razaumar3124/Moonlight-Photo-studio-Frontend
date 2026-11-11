from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    designs,
    frame_materials,
    frames,
    geometry,
    health,
    photos,
    quotes,
    templates,
)

api_v1_router = APIRouter()

# Register Phase 1 endpoints
api_v1_router.include_router(health.router)

# Register Phase 2 endpoints
api_v1_router.include_router(auth.router)

# Register Phase 3 endpoints
api_v1_router.include_router(frame_materials.router)
api_v1_router.include_router(frames.router)
api_v1_router.include_router(templates.router)

# Register Phase 4 endpoints
api_v1_router.include_router(photos.router)

# Register Phase 5 endpoints
api_v1_router.include_router(geometry.router)

# Register Phase 6 endpoints
api_v1_router.include_router(designs.router)

# Register Phase 7 endpoints (WhatsApp Quotes & Digital Design Reports)
api_v1_router.include_router(quotes.router)
