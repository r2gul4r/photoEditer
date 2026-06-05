from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.models.schemas import AnalyzeImageResponse
from app.services.image_analysis import analyze_image
from app.services.image_store import image_store
from app.services.metadata import read_metadata
from app.services.raw_analysis import analyze_raw, render_raw_to_rgb
from app.utils.image_io import SUPPORTED_EXTENSIONS, downscale, infer_file_type, load_rgb_image

router = APIRouter(prefix="/api/images", tags=["images"])


async def read_limited_upload(file: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=413, detail=f"Uploaded file exceeds {max_bytes // (1024 * 1024)}MB limit")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/analyze", response_model=AnalyzeImageResponse)
async def analyze_upload(file: UploadFile = File(...)) -> AnalyzeImageResponse:
    file_type = infer_file_type(file.filename or "upload")
    if file_type not in {*SUPPORTED_EXTENSIONS.values(), "raw"}:
        raise HTTPException(status_code=415, detail=f"Unsupported file type for MVP: {file_type}")

    content = await read_limited_upload(file, settings.max_upload_bytes)
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    record = image_store.save_upload(file.filename or "upload", content)
    raw_result = None
    try:
        if record.file_type == "raw":
            raw_result = analyze_raw(record.original_path)
            if not raw_result.get("ok"):
                raise HTTPException(status_code=422, detail=raw_result)
            image = render_raw_to_rgb(record.original_path)
        else:
            image = load_rgb_image(record.original_path)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Cannot read image: {exc}") from exc

    source_preview_path = image_store.preview_path(record.image_id, "source")
    downscale(image.convert("RGB"), settings.preview_max_side).save(source_preview_path, format="JPEG", quality=90)

    response = AnalyzeImageResponse(
        image_id=record.image_id,
        filename=record.filename,
        file_type=record.file_type,
        width=image.width,
        height=image.height,
        source_preview_url=f"/api/previews/{source_preview_path.name}",
        metadata=read_metadata(record.original_path),
        analysis=analyze_image(image),
        raw_analysis=raw_result,
    )
    image_store.set_response(record.image_id, response)
    return response
