from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.models.schemas import ExportPresetRequest

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

