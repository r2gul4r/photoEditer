from fastapi import APIRouter, HTTPException

from app.models.schemas import ReferenceLibraryResponse
from app.services.reference_library import ReferenceLibraryError, load_reference_library

router = APIRouter(prefix="/api/references", tags=["references"])


@router.get("", response_model=ReferenceLibraryResponse)
def list_references() -> ReferenceLibraryResponse:
    try:
        return load_reference_library()
    except ReferenceLibraryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
