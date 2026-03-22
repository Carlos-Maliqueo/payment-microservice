from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.session import get_session
import redis.asyncio as aioredis
from app.core.config import settings

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/")
async def health_check():
    return {"status": "ok", "service": "payment-microservice"}


@router.get("/detailed")
async def detailed_health(session: AsyncSession = Depends(get_session)):
    checks = {}

    # DB check
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"

    # Redis check
    try:
        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}