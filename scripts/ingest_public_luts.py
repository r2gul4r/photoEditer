from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.lut_analysis import LutAnalysisError, ingest_lut_url  # noqa: E402


PathFilter = Callable[[str], bool]


def _tree_paths(api_url: str) -> list[str]:
    request = urllib.request.Request(api_url, headers={"User-Agent": "TonePilotLocal/0.1 public-lut-ingest"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return sorted(item["path"] for item in payload["tree"] if item.get("type") == "blob" and item["path"].lower().endswith(".cube"))


def _raw_url(prefix: str, path: str) -> str:
    return prefix + urllib.parse.quote(path, safe="/")


def _concept_from_path(path: str) -> str:
    stem = Path(path).stem
    folder = Path(path).parent.name
    text = f"{folder} {stem}" if folder not in {".", ""} else stem
    return text.replace("_", " ").replace("-", " ").replace("&", "and").strip()


def _abpy_srgb_only(path: str) -> bool:
    return path.endswith("_sRGB.cube") or path.endswith(" sRGB.cube")


SOURCES: tuple[dict[str, object], ...] = (
    {
        "id": "abpy-fujifilm-camera-profiles",
        "api_url": "https://api.github.com/repos/abpy/FujifilmCameraProfiles/git/trees/master?recursive=1",
        "raw_prefix": "https://raw.githubusercontent.com/abpy/FujifilmCameraProfiles/master/",
        "filter": _abpy_srgb_only,
    },
    {
        "id": "shenmintao-v-log-alchemy",
        "api_url": "https://api.github.com/repos/shenmintao/V-Log-Alchemy/git/trees/main?recursive=1",
        "raw_prefix": "https://raw.githubusercontent.com/shenmintao/V-Log-Alchemy/main/",
        "filter": lambda path: path.startswith("Luts/"),
    },
    {
        "id": "openshot-rec709-luts",
        "api_url": "https://api.github.com/repos/OpenShot/openshot-qt/git/trees/develop?recursive=1",
        "raw_prefix": "https://raw.githubusercontent.com/OpenShot/openshot-qt/develop/",
        "filter": lambda path: path.startswith("src/colors/"),
    },
)


def main() -> int:
    total = 0
    errors: list[str] = []
    for source in SOURCES:
        source_id = str(source["id"])
        path_filter = source["filter"]
        assert callable(path_filter)
        paths = [path for path in _tree_paths(str(source["api_url"])) if path_filter(path)]
        print(f"{source_id}: {len(paths)} LUTs selected")
        for path in paths:
            url = _raw_url(str(source["raw_prefix"]), path)
            try:
                response = ingest_lut_url(url, concept=_concept_from_path(path))
            except LutAnalysisError as exc:
                errors.append(f"{source_id}: {path}: {exc}")
                continue
            total += 1
            print(f"  ok {response.profilePath}")

    print(f"ingested={total}")
    if errors:
        print("errors:")
        for error in errors:
            print(f"  {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
