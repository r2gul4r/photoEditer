from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.schemas import AnalyzeImageResponse
from app.services.image_analysis import analyze_image
from app.services.image_store import image_store
from app.services.metadata import read_metadata
from app.utils.image_io import SUPPORTED_EXTENSIONS, infer_file_type, load_rgb_image

router = APIRouter(prefix="/api/images", tags=["images"])


@router.post("/analyze", response_model=AnalyzeImageResponse)
async def analyze_upload(file: UploadFile = File(...)) -> AnalyzeImageResponse:
    file_type = infer_file_type(file.filename or "upload")
    if file_type not in set(SUPPORTED_EXTENSIONS.values()):
        raise HTTPException(status_code=415, detail=f"Unsupported file type for MVP: {file_type}")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    record = image_store.save_upload(file.filename or "upload", content)
    try:
        image = load_rgb_image(record.original_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Cannot read image: {exc}") from exc

    response = AnalyzeImageResponse(
        image_id=record.image_id,
        filename=record.filename,
        file_type=record.file_type,
        width=image.width,
        height=image.height,
        metadata=read_metadata(record.original_path),
        analysis=analyze_image(image),
    )
    image_store.set_response(record.image_id, response)
    return response

