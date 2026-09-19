from fastapi import APIRouter

from documind.api.routes import HEALTH

router = APIRouter(tags=["health"])


@router.get(HEALTH)
async def get_health() -> dict[str, str]:
    return {"status": "ok"}
