from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.config import settings
from app.models.schemas import AnalyzeImageResponse
from app.utils.image_io import infer_file_type


@dataclass
class ImageRecord:
    image_id: str
    filename: str
    file_type: str
    original_path: Path
    response: AnalyzeImageResponse | None = None


class ImageStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.originals_dir = root / "originals"
        self.previews_dir = root / "previews"
        self.records: dict[str, ImageRecord] = {}
        self.originals_dir.mkdir(parents=True, exist_ok=True)
        self.previews_dir.mkdir(parents=True, exist_ok=True)

    def save_upload(self, filename: str, content: bytes) -> ImageRecord:
        image_id = str(uuid4())
        suffix = Path(filename).suffix.lower() or ".img"
        original_path = self.originals_dir / f"{image_id}{suffix}"
        original_path.write_bytes(content)
        record = ImageRecord(
            image_id=image_id,
            filename=Path(filename).name,
            file_type=infer_file_type(filename),
            original_path=original_path,
        )
        self.records[image_id] = record
        return record

    def set_response(self, image_id: str, response: AnalyzeImageResponse) -> None:
        self.get(image_id).response = response

    def get(self, image_id: str) -> ImageRecord:
        try:
            return self.records[image_id]
        except KeyError as exc:
            raise KeyError(f"Unknown image_id: {image_id}") from exc

    def preview_path(self, image_id: str, candidate_id: str) -> Path:
        safe_candidate = "".join(ch for ch in candidate_id if ch.isalnum() or ch in {"-", "_"}) or "preview"
        return self.previews_dir / f"{image_id}-{safe_candidate}.jpg"


image_store = ImageStore(settings.storage_dir)

