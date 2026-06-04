from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models.schemas import (
    LutIngestResponse,
    LutProfileListResponse,
    LutSourceRegistry,
    LutStyleIndexResponse,
    LutUrlIngestRequest,
    PresetProfileListResponse,
    PresetSourceRegistry,
    PresetStyleIndexResponse,
    ReferenceLibraryResponse,
)
from app.services.lut_analysis import (
    LutAnalysisError,
    LutSourcePolicyError,
    ingest_lut_bytes,
    ingest_lut_url,
    load_lut_source_registry,
    load_lut_style_profiles,
)
from app.services.lut_style_index import load_lut_style_index
from app.services.preset_analysis import (
    PresetAnalysisError,
    load_preset_source_registry,
    load_preset_style_profiles,
)
from app.services.preset_style_index import load_preset_style_index
from app.services.reference_library import ReferenceLibraryError, load_reference_library

router = APIRouter(prefix="/api/references", tags=["references"])


@router.get("", response_model=ReferenceLibraryResponse)
def list_references() -> ReferenceLibraryResponse:
    try:
        return load_reference_library()
    except ReferenceLibraryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/luts/sources", response_model=LutSourceRegistry)
def list_lut_sources() -> LutSourceRegistry:
    try:
        return load_lut_source_registry()
    except LutAnalysisError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/luts/profiles", response_model=LutProfileListResponse)
def list_lut_profiles() -> LutProfileListResponse:
    try:
        return load_lut_style_profiles()
    except LutAnalysisError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/luts/style-index", response_model=LutStyleIndexResponse)
def get_lut_style_index() -> LutStyleIndexResponse:
    try:
        return LutStyleIndexResponse(index=load_lut_style_index())
    except LutAnalysisError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/presets/sources", response_model=PresetSourceRegistry)
def list_preset_sources() -> PresetSourceRegistry:
    try:
        return load_preset_source_registry()
    except PresetAnalysisError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/presets/profiles", response_model=PresetProfileListResponse)
def list_preset_profiles() -> PresetProfileListResponse:
    try:
        return load_preset_style_profiles()
    except PresetAnalysisError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/presets/style-index", response_model=PresetStyleIndexResponse)
def get_preset_style_index() -> PresetStyleIndexResponse:
    try:
        return PresetStyleIndexResponse(index=load_preset_style_index())
    except PresetAnalysisError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/luts/import", response_model=LutIngestResponse)
async def import_lut_profile(
    file: UploadFile = File(...),
    concept: str | None = Form(default=None),
    source_url: str | None = Form(default=None),
    license_name: str | None = Form(default=None),
) -> LutIngestResponse:
    content = await file.read()
    try:
        return ingest_lut_bytes(
            content,
            filename=file.filename or "upload.cube",
            concept=concept,
            source_url=source_url,
            license_name=license_name,
        )
    except LutAnalysisError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/luts/ingest-url", response_model=LutIngestResponse)
def ingest_lut_profile_from_url(request: LutUrlIngestRequest) -> LutIngestResponse:
    try:
        return ingest_lut_url(request.sourceUrl, concept=request.concept)
    except LutSourcePolicyError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LutAnalysisError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
