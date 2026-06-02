from fastapi import APIRouter
from fastapi import HTTPException
from fastapi.responses import FileResponse, JSONResponse

from app.models.schemas import ExportPresetRequest, ExportRenderedImageRequest
from app.services.image_store import image_store
from app.services.raw_analysis import render_raw_to_rgb
from app.services.renderer import render_preview
from app.utils.image_io import load_rgb_image

router = APIRouter(prefix="/api/export", tags=["export"])


@router.post("/preset-json")
def export_preset_json(request: ExportPresetRequest) -> JSONResponse:
    filename = f"tonepilot-{request.candidate.id}.json"
    return JSONResponse(
        content={
            "app": "TonePilot Local",
            "version": "0.1.0",
            "image_id": request.image_id,
            "style_prompt": request.style_prompt,
            "candidate": request.candidate.model_dump(),
        },
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/rendered-image")
def export_rendered_image(request: ExportRenderedImageRequest) -> FileResponse:
    try:
        record = image_store.get(request.image_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        image = render_raw_to_rgb(record.original_path) if record.file_type == "raw" else load_rgb_image(record.original_path)
        rendered = render_preview(image, request.adjustments)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Cannot render export image: {exc}") from exc

    suffix = "jpg" if request.format == "jpeg" else "png"
    output_path = image_store.previews_dir / f"{request.image_id}-{request.candidate_id}-export.{suffix}"
    if request.format == "jpeg":
        rendered.save(output_path, format="JPEG", quality=94)
        media_type = "image/jpeg"
    else:
        rendered.save(output_path, format="PNG")
        media_type = "image/png"

    return FileResponse(
        output_path,
        media_type=media_type,
        filename=f"tonepilot-{request.candidate_id}.{suffix}",
    )
