from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.models.schemas import PreviewRequest, PreviewResponse
from app.services.image_store import image_store
from app.services.raw_analysis import render_raw_to_rgb
from app.services.renderer import render_preview
from app.utils.image_io import load_rgb_image

router = APIRouter(prefix="/api", tags=["preview"])


@router.post("/preview", response_model=PreviewResponse)
def preview(request: PreviewRequest) -> PreviewResponse:
    try:
        record = image_store.get(request.image_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        image = render_raw_to_rgb(record.original_path) if record.file_type == "raw" else load_rgb_image(record.original_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Cannot render source image: {exc}") from exc
    rendered = render_preview(image, request.adjustments)
    output_path = image_store.preview_path(request.image_id, request.candidate_id)
    rendered.save(output_path, format="JPEG", quality=90)
    return PreviewResponse(preview_url=f"/api/previews/{output_path.name}")


@router.get("/previews/{filename}")
def get_preview(filename: str) -> FileResponse:
    path = image_store.previews_dir / filename
    if not path.exists() or path.parent != image_store.previews_dir:
        raise HTTPException(status_code=404, detail="Preview not found")
    return FileResponse(path, media_type="image/jpeg")
