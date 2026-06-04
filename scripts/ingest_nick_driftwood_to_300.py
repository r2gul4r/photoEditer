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


TARGET_PROFILE_COUNT = 300

PACKS = (
    ("https://www.nickdriftwood.com/wp-content/uploads/2023/04/Wedding_LUT_Pack_Nick_Driftwood.zip", "nick driftwood wedding"),
    ("https://www.nickdriftwood.com/wp-content/uploads/2023/02/Dope709v105.zip", "nick driftwood dope709 v105"),
    ("https://www.nickdriftwood.com/wp-content/uploads/2023/02/Dope709_v104.zip", "nick driftwood dope709 v104"),
    ("https://www.nickdriftwood.com/wp-content/uploads/2023/04/RGBMAN.zip", "nick driftwood rgbman"),
    ("https://www.nickdriftwood.com/wp-content/uploads/2023/06/DWD_Lumix-S5II-X-v3-LUT-Pack.zip", "nick driftwood lumix s5iix v3"),
    ("https://www.nickdriftwood.com/wp-content/uploads/2023/03/Driftwood-Kodakchrome-64-v1-Look-LUT-Pack.zip", "nick driftwood kodakchrome 64"),
    ("https://www.nickdriftwood.com/wp-content/uploads/2024/11/Goldilocks-False-Color-by-Nick-Driftwood.cube.zip", "nick driftwood goldilocks false color"),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _profile_count() -> int:
    return len(list((PROJECT_ROOT / "reference" / "luts" / "profiles").glob("*.json")))


def _download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "TonePilotLocal/0.1 nick-driftwood-targeted-lut-ingest"})
    with urlopen(request, timeout=90) as response:
        return response.read()


def _cube_entries(content: bytes, prefix: str = "") -> list[tuple[str, bytes]]:
    entries: list[tuple[str, bytes]] = []
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for info in sorted(archive.infolist(), key=lambda item: item.filename):
            if info.is_dir():
                continue
            parts = Path(info.filename).parts
            if "__MACOSX" in parts or Path(info.filename).name.startswith("._"):
                continue
            name = f"{prefix}{info.filename}"
            lower = info.filename.lower()
            payload = archive.read(info)
            if lower.endswith(".zip"):
                entries.extend(_cube_entries(payload, prefix=f"{name}/"))
            elif lower.endswith(".cube"):
                entries.append((name, payload))
    return entries


def _concept(prefix: str, name: str) -> str:
    stem = Path(name).stem
    folder = Path(name).parent.name
    text = f"{folder} {stem}" if folder not in {"", "."} else stem
    return f"{prefix} {text}".replace("_", " ").replace("-", " ").strip()


def main() -> int:
    start_count = _profile_count()
    if start_count >= TARGET_PROFILE_COUNT:
        print(f"already_at_target={start_count}")
        return 0

    for url, prefix in PACKS:
        downloaded_at = _utc_now()
        entries = _cube_entries(_download(url))
        print(f"{prefix}: {len(entries)} cube files")
        for entry_name, payload in entries:
            before = _profile_count()
            if before >= TARGET_PROFILE_COUNT:
                print(f"target_reached={before}")
                return 0

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
            after = _profile_count()
            added = after - before
            print(f"ok added={added} count={after} {response.profilePath}")

    final_count = _profile_count()
    print(f"final_count={final_count}")
    return 0 if final_count == TARGET_PROFILE_COUNT else 1


if __name__ == "__main__":
    raise SystemExit(main())
