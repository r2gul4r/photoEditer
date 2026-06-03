from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.models.schemas import ReferenceLibraryResponse, ReferenceManifest


class ReferenceLibraryError(RuntimeError):
    pass


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _reference_root() -> Path:
    return _project_root() / "reference"


def _relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _mark_exists(payload: dict[str, Any], reference_root: Path) -> dict[str, Any]:
    source = payload.get("source")
    if isinstance(source, dict):
        source_path = source.get("path")
        source["exists"] = bool(isinstance(source_path, str) and (reference_root / source_path).exists())

    targets = payload.get("targets")
    if isinstance(targets, list):
        for target in targets:
            if not isinstance(target, dict):
                continue
            target_path = target.get("path")
            target["exists"] = bool(isinstance(target_path, str) and (reference_root / target_path).exists())

    preset = payload.get("preset")
    if isinstance(preset, dict):
        preset_path = preset.get("path")
        preset["exists"] = bool(isinstance(preset_path, str) and (reference_root / preset_path).exists())

    return payload


def load_reference_library(reference_root: Path | None = None) -> ReferenceLibraryResponse:
    root = reference_root or _reference_root()
    manifests_dir = root / "manifests"
    if not manifests_dir.exists():
        return ReferenceLibraryResponse(count=0, items=[])

    items: list[ReferenceManifest] = []
    for manifest_path in sorted(manifests_dir.glob("*.json")):
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ReferenceLibraryError(f"Cannot read reference manifest {manifest_path.name}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ReferenceLibraryError(f"Invalid reference manifest JSON {manifest_path.name}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ReferenceLibraryError(f"Reference manifest {manifest_path.name} must be a JSON object")

        payload = dict(payload)
        payload["manifest_path"] = _relative_path(manifest_path, root)
        try:
            items.append(ReferenceManifest.model_validate(_mark_exists(payload, root)))
        except ValidationError as exc:
            raise ReferenceLibraryError(f"Invalid reference manifest {manifest_path.name}: {exc}") from exc

    return ReferenceLibraryResponse(count=len(items), items=items)
