from fastapi import APIRouter

from app.models.schemas import RawSupportStatus
from app.services.raw_analysis import raw_support_status

router = APIRouter(prefix="/api/raw", tags=["raw"])


@router.get("/status", response_model=RawSupportStatus)
def status() -> RawSupportStatus:
    return raw_support_status()
