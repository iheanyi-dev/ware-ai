from fastapi import FastAPI

from app.core.config import get_settings

# Settings are loaded once at module import time — cached by get_settings(),
# so this doesn't re-read .env on every request.
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Recommendation + Chatbot AI microservice for the education platform",
    version="0.1.0",
)


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