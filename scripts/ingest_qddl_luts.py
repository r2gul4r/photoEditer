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


QDDL_PACKS = (
    "https://www.photoshoplus.fr/download/q-ddl-color-luts-cinematic-5-packs/?tmstv=1780543774",
    "https://www.photoshoplus.fr/download/q-ddl-color-luts-color-grading-5-packs/?tmstv=1780543774",
    "https://www.photoshoplus.fr/download/q-ddl-color-luts-color-moods-5-packs/?tmstv=1780543774",
    "https://www.photoshoplus.fr/download/q-ddl-color-luts-film-simulation-5-packs/?tmstv=1780543774",
)


def _download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "TonePilotLocal/0.1 public-lut-ingest"})
    with urlopen(request, timeout=90) as response:
        return response.read()


def _cube_entries_from_zip(content: bytes, prefix: str = "") -> list[tuple[str, bytes]]:
    entries: list[tuple[str, bytes]] = []
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for info in sorted(archive.infolist(), key=lambda item: item.filename):
            if info.is_dir():
                continue
            name = f"{prefix}{info.filename}"
            payload = archive.read(info)
            lower = info.filename.lower()
            if lower.endswith(".zip"):
                entries.extend(_cube_entries_from_zip(payload, prefix=f"{name}/"))
            elif lower.endswith(".cube"):
                entries.append((name, payload))
    return entries


def _concept_from_name(name: str) -> str:
    stem = Path(name).stem
    parent = Path(name).parent.name
    text = f"q-ddl {parent} {stem}" if parent not in {".", ""} else f"q-ddl {stem}"
    return text.replace("_", " ").replace("-", " ").replace("&", "and").strip()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    limit = 50
    ingested = 0
    for pack_url in QDDL_PACKS:
        if ingested >= limit:
            break
        pack = _download(pack_url)
        for entry_name, payload in _cube_entries_from_zip(pack):
            if ingested >= limit:
                break
            response = ingest_lut_bytes(
                payload,
                filename=Path(entry_name).name,
                concept=_concept_from_name(entry_name),
                source_url=f"{pack_url}#{entry_name}",
                license_name="CC-BY-4.0",
                status="allow",
                source_type="allowed_public_lut",
                downloaded_at=_utc_now(),
            )
            ingested += 1
            print(f"ok {ingested:02d} {response.profilePath}")
    print(f"ingested={ingested}")
    return 0 if ingested == limit else 1


if __name__ == "__main__":
    raise SystemExit(main())
