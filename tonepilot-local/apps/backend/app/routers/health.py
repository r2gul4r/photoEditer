from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("/health")
def health() -> dict[str, bool | str]:
    return {"ok": True, "service": settings.service_name}

