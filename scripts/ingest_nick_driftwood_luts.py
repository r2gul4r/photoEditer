from __future__ import annotations

import io
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.lut_analysis import ingest_lut_bytes  # noqa: E402


PACKS = (
    ("https://nickdriftwood.com/wp-content/uploads/2023/01/Driftwood-S5II-LUT-FREE.zip", "nick driftwood lumix s5ii hi precision"),
    ("https://www.nickdriftwood.com/wp-content/uploads/2024/11/FREE-Real-Time-LUT-PAck-from-Nick-Driftwood.zip", "nick driftwood free real time lut"),
    ("https://www.nickdriftwood.com/wp-content/uploads/2023/04/PastelKrome-Series.zip", "nick driftwood pastelkrome"),
    ("https://www.nickdriftwood.com/wp-content/uploads/2023/03/Driftwood_Beauty_LUT-Series.zip", "nick driftwood beauty"),
    ("https://www.nickdriftwood.com/wp-content/uploads/2023/04/LikePhotoV2.zip", "nick driftwood likephotov2"),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "TonePilotLocal/0.1 nick-driftwood-lut-ingest"})
    with urlopen(request, timeout=90) as response:
        return response.read()


def _cube_entries(content: bytes, prefix: str = "") -> list[tuple[str, bytes]]:
    entries: list[tuple[str, bytes]] = []
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for info in sorted(archive.infolist(), key=lambda item: item.filename):
            if info.is_dir():
                continue
            name = f"{prefix}{info.filename}"
            lower = info.filename.lower()
            parts = Path(info.filename).parts
            if "__MACOSX" in parts or Path(info.filename).name.startswith("._"):
                continue
            if lower.endswith(".zip"):
                entries.extend(_cube_entries(archive.read(info), prefix=f"{name}/"))
            elif lower.endswith(".cube"):
                entries.append((name, archive.read(info)))
    return entries


def _concept(prefix: str, name: str) -> str:
    stem = Path(name).stem
    folder = Path(name).parent.name
    text = f"{folder} {stem}" if folder not in {"", "."} else stem
    return f"{prefix} {text}".replace("_", " ").replace("-", " ").strip()


def main() -> int:
    total = 0
    for url, prefix in PACKS:
        downloaded_at = _utc_now()
        entries = _cube_entries(_download(url))
        print(f"{prefix}: {len(entries)} cube files")
        for entry_name, payload in entries:
            response = ingest_lut_bytes(
                payload,
                filename=Path(entry_name).name,
                concept=_concept(prefix, entry_name),
                source_url=f"{url}#{entry_name}",
                license_name="free public creator download",
                status="allow",
                source_type="allowed_public_lut",
                downloaded_at=downloaded_at,
            )
            total += 1
            print(f"ok {response.profilePath}")
    print(f"ingested={total}")
    return 0 if total > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
