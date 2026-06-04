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


CREATOR_LUTS = (
    ("https://eww.pavc.panasonic.co.jp/nwbgosm/Lumix/DAY_FOR_NIGHT_Jon_Simo.zip", "lumix creator day for night by Jon Simo"),
    ("https://eww.pavc.panasonic.co.jp/nwbgosm/Lumix/GRITTY_CINEMA_Jon_Simo.zip", "lumix creator gritty cinema by Jon Simo"),
    ("https://eww.pavc.panasonic.co.jp/nwbgosm/Lumix/VINTAGE_VIBES_Jon_Simo.zip", "lumix creator vintage vibes by Jon Simo"),
    ("https://eww.pavc.panasonic.co.jp/nwbgosm/Lumix/Faded_Summer_Caleb_Hoover.zip", "lumix creator faded summer by Caleb Hoover"),
    ("https://eww.pavc.panasonic.co.jp/nwbgosm/Lumix/Chasm_Lake_Devon_Williams.zip", "lumix creator chasm lake by Devon Williams"),
    ("https://eww.pavc.panasonic.co.jp/nwbgosm/Lumix/Dark_Floral_Devon_Williams.zip", "lumix creator dark floral by Devon Williams"),
    ("https://eww.pavc.panasonic.co.jp/nwbgosm/Lumix/Dusty_Earth_Devon_Williams.zip", "lumix creator dusty earth by Devon Williams"),
    ("https://eww.pavc.panasonic.co.jp/nwbgosm/Lumix/Leafy_Greens_Devon_Williams.zip", "lumix creator leafy greens by Devon Williams"),
    ("https://eww.pavc.panasonic.co.jp/nwbgosm/Lumix/Lock_Box_Forest_Devon_Williams.zip", "lumix creator lock box forest by Devon Williams"),
)

VARICAM_EE_URL = "https://pro-av.panasonic.net/en/cinema_camera_varicam_eva/support/lut/data/VariCam_33-Grading_Cube_LUTs_E-E.zip"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "TonePilotLocal/0.1 panasonic-lut-ingest"})
    with urlopen(request, timeout=90) as response:
        return response.read()


def _cube_entries_from_zip(content: bytes) -> list[tuple[str, bytes]]:
    entries: list[tuple[str, bytes]] = []
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for info in sorted(archive.infolist(), key=lambda item: item.filename):
            if info.is_dir():
                continue
            payload = archive.read(info)
            lower = info.filename.lower()
            if lower.endswith(".zip"):
                for nested_name, nested_payload in _cube_entries_from_zip(payload):
                    entries.append((f"{info.filename}/{nested_name}", nested_payload))
            elif lower.endswith(".cube"):
                entries.append((info.filename, payload))
    return entries


def _concept_from_entry(prefix: str, name: str) -> str:
    stem = Path(name).stem
    parent = Path(name).parent.name
    base = f"{parent} {stem}" if parent not in {"", "."} else stem
    return f"{prefix} {base}".replace("_", " ").replace("-", " ").strip()


def _ingest_zip(url: str, *, concept_prefix: str, license_name: str) -> int:
    count = 0
    downloaded_at = _utc_now()
    for entry_name, payload in _cube_entries_from_zip(_download(url)):
        response = ingest_lut_bytes(
            payload,
            filename=Path(entry_name).name,
            concept=_concept_from_entry(concept_prefix, entry_name),
            source_url=f"{url}#{entry_name}",
            license_name=license_name,
            status="allow",
            source_type="allowed_public_lut",
            downloaded_at=downloaded_at,
        )
        count += 1
        print(f"ok {response.profilePath}")
    return count


def main() -> int:
    total = 0
    for url, concept in CREATOR_LUTS:
        total += _ingest_zip(url, concept_prefix=concept, license_name="Panasonic public download")
    total += _ingest_zip(VARICAM_EE_URL, concept_prefix="panasonic varicam ee", license_name="Panasonic public download")
    print(f"ingested={total}")
    return 0 if total > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
