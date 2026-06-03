from fastapi import APIRouter

from app.models.schemas import AiConnectionStatus
from app.services.codex_app_server import probe_codex_app_server

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/status", response_model=AiConnectionStatus)
def status() -> AiConnectionStatus:
    return probe_codex_app_server()
