
from fastapi import FastAPI

from app.core.config import get_settings
import logging
logging.basicConfig(level=logging.INFO)

from app.api.routes.recommendations import router as recommendations_router
from app.api.routes.chat import router as chat_router
from app.api.routes.admin import router as crawl_router
# app/main.py
from app.api.routes import sync

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Recommendation + Chatbot AI microservice for the education platform",
    version="0.1.0",
)
app.include_router(sync.router)
app.include_router(chat_router)

app.include_router(recommendations_router)

app.include_router(crawl_router)

@app.get("/health", tags=["system"])
def health_check() -> dict:
    """
    Basic liveness check — confirms the service is up and reachable.
    No authentication required, since uptime monitors and load balancers
    need to hit this without credentials.
    """
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
    }


# Routers for /api/recommendations and /api/chatbot get registered here
# with app.include_router(...) starting Phase 4 and Phase 5, once those
# services actually exist. Intentionally not present yet in Phase 0.