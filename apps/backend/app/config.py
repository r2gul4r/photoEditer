from pathlib import Path
import os

from pydantic import BaseModel


class Settings(BaseModel):
    service_name: str = "tonepilot-backend"
    storage_dir: Path = Path(os.getenv("TONEPILOT_STORAGE_DIR", Path(__file__).resolve().parents[1] / ".tonepilot-data"))
    preview_max_side: int = int(os.getenv("TONEPILOT_PREVIEW_MAX_SIDE", "1600"))
    max_upload_bytes: int = int(os.getenv("TONEPILOT_MAX_UPLOAD_BYTES", str(200 * 1024 * 1024)))
    codex_command: str = os.getenv("TONEPILOT_CODEX_COMMAND", "codex")
    codex_timeout_seconds: float = float(os.getenv("TONEPILOT_CODEX_TIMEOUT_SECONDS", "90"))
    allowed_origins: list[str] = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]
    allowed_origin_regex: str | None = os.getenv(
        "TONEPILOT_ALLOWED_ORIGIN_REGEX",
        r"^http://(127\.0\.0\.1|localhost):51[0-9]{2}$",
    )


settings = Settings()
