from __future__ import annotations

import colorsys
import hashlib
import json
import re
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Any
from uuid import uuid4

import numpy as np
from pydantic import ValidationError

from app.models.schemas import (
    LutIngestResponse,
    LutProfileListResponse,
    LutProfileMetadata,
    LutSourceEntry,
    LutSourceRegistry,
    LutStyleProfile,
)


MAX_LUT_BYTES = 16 * 1024 * 1024


class LutAnalysisError(RuntimeError):
    pass


class LutSourcePolicyError(LutAnalysisError):
    pass


@dataclass(frozen=True)
class CubeLut:
    title: str | None
    size: int
    domain_min: np.ndarray
    domain_max: np.ndarray
    table: np.ndarray


DownloadFn = Callable[[str], bytes]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _reference_root() -> Path:
    return _project_root() / "reference"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_stem(filename: str) -> str:
    stem = Path(filename).stem.strip().lower() or "lut"
    safe = re.sub(r"[^a-z0-9._-]+", "-", stem).strip("-._")
    return safe[:80] or "lut"


def _relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _strip_inline_comment(line: str) -> str:
    if "#" not in line:
        return line
    return line.split("#", 1)[0].strip()


def _decode_cube_text(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("cp1252", errors="replace")


def parse_cube_lut(text: str) -> CubeLut:
    title: str | None = None
    size: int | None = None
    domain_min = np.array([0.0, 0.0, 0.0], dtype=np.float32)
    domain_max = np.array([1.0, 1.0, 1.0], dtype=np.float32)
    rows: list[list[float]] = []

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        command = line.split(maxsplit=1)[0].upper()
        if command == "TITLE":
            title = line[len("TITLE") :].strip().strip('"')
            continue

        line = _strip_inline_comment(line)
        if not line:
            continue

        parts = line.split()
        command = parts[0].upper()

        if command == "LUT_3D_SIZE":
            if len(parts) != 2:
                raise LutAnalysisError(f"LUT_3D_SIZE must have one integer value at line {line_number}")
            size = int(parts[1])
            if size < 2 or size > 128:
                raise LutAnalysisError("Only 3D LUT sizes from 2 to 128 are supported")
            continue

        if command == "LUT_1D_SIZE":
            raise LutAnalysisError("1D .cube LUTs are not supported for style profile extraction yet")

        if command in {"DOMAIN_MIN", "DOMAIN_MAX"}:
            if len(parts) != 4:
                raise LutAnalysisError(f"{command} must have three numeric values at line {line_number}")
            values = np.array([float(value) for value in parts[1:]], dtype=np.float32)
            if command == "DOMAIN_MIN":
                domain_min = values
            else:
                domain_max = values
            continue

        if command == "LUT_3D_INPUT_RANGE":
            if len(parts) != 3:
                raise LutAnalysisError(f"{command} must have two numeric values at line {line_number}")
            low = float(parts[1])
            high = float(parts[2])
            domain_min = np.array([low, low, low], dtype=np.float32)
            domain_max = np.array([high, high, high], dtype=np.float32)
            continue

        if len(parts) != 3:
            raise LutAnalysisError(f"Unexpected .cube content at line {line_number}: {raw_line}")
        try:
            rows.append([float(value) for value in parts])
        except ValueError as exc:
            raise LutAnalysisError(f"Invalid RGB row at line {line_number}: {raw_line}") from exc

    if size is None:
        raise LutAnalysisError("Missing LUT_3D_SIZE")

    expected = size**3
    if len(rows) != expected:
        raise LutAnalysisError(f"LUT_3D_SIZE {size} requires {expected} RGB rows, found {len(rows)}")

    if np.any(domain_max <= domain_min):
        raise LutAnalysisError("DOMAIN_MAX values must be greater than DOMAIN_MIN values")

    table = np.asarray(rows, dtype=np.float32).reshape((size, size, size, 3))
    table = np.clip(table, 0.0, 1.0)
    return CubeLut(title=title or None, size=size, domain_min=domain_min, domain_max=domain_max, table=table)


def _input_grid(size: int) -> np.ndarray:
    axis = np.linspace(0.0, 1.0, size, dtype=np.float32)
    blue, green, red = np.meshgrid(axis, axis, axis, indexing="ij")
    return np.stack([red, green, blue], axis=-1)


def apply_lut(lut: CubeLut, rgb: np.ndarray) -> np.ndarray:
    values = np.asarray(rgb, dtype=np.float32)
    original_shape = values.shape
    points = values.reshape((-1, 3))
    domain_span = lut.domain_max - lut.domain_min
    normalized = np.clip((points - lut.domain_min) / domain_span, 0.0, 1.0)
    positions = normalized * (lut.size - 1)
    lower = np.floor(positions).astype(int)
    upper = np.clip(lower + 1, 0, lut.size - 1)
    frac = positions - lower

    r0, g0, b0 = lower[:, 0], lower[:, 1], lower[:, 2]
    r1, g1, b1 = upper[:, 0], upper[:, 1], upper[:, 2]
    fr, fg, fb = frac[:, 0:1], frac[:, 1:2], frac[:, 2:3]

    c000 = lut.table[b0, g0, r0]
    c100 = lut.table[b0, g0, r1]
    c010 = lut.table[b0, g1, r0]
    c110 = lut.table[b0, g1, r1]
    c001 = lut.table[b1, g0, r0]
    c101 = lut.table[b1, g0, r1]
    c011 = lut.table[b1, g1, r0]
    c111 = lut.table[b1, g1, r1]

    c00 = c000 * (1 - fr) + c100 * fr
    c10 = c010 * (1 - fr) + c110 * fr
    c01 = c001 * (1 - fr) + c101 * fr
    c11 = c011 * (1 - fr) + c111 * fr
    c0 = c00 * (1 - fg) + c10 * fg
    c1 = c01 * (1 - fg) + c11 * fg
    output = c0 * (1 - fb) + c1 * fb
    return output.reshape(original_shape)


def _luma(rgb: np.ndarray) -> np.ndarray:
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def _round(value: float, places: int = 4) -> float:
    return round(float(value), places)


def _rgb_to_hsv(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values.reshape((-1, 3)), 0.0, 1.0)
    return np.asarray([colorsys.rgb_to_hsv(float(r), float(g), float(b)) for r, g, b in clipped], dtype=np.float32)


def _hue_delta_degrees(input_hue: float, output_hue: float) -> float:
    delta = (output_hue - input_hue + 0.5) % 1.0 - 0.5
    return float(delta * 360.0)


def _tone_features(lut: CubeLut) -> dict[str, Any]:
    levels = np.array([0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0], dtype=np.float32)
    gray = np.stack([levels, levels, levels], axis=-1)
    mapped = apply_lut(lut, gray)
    output_luma = _luma(mapped)
    delta = output_luma - levels
    points = [{"input": _round(level), "output": _round(output)} for level, output in zip(levels, output_luma)]

    return {
        "curve": points,
        "black_point": _round(output_luma[0]),
        "white_point": _round(output_luma[-1]),
        "shadow_lift": _round(float(np.mean(delta[1:3]))),
        "midtone_lift": _round(delta[3]),
        "highlight_lift": _round(float(np.mean(delta[4:6]))),
        "contrast_delta": _round((output_luma[5] - output_luma[1]) - 0.8),
    }


def _balance_features(inputs: np.ndarray, outputs: np.ndarray) -> dict[str, Any]:
    channel_delta = np.mean(outputs - inputs, axis=0)
    temperature_shift = channel_delta[0] - channel_delta[2]
    tint_shift = ((channel_delta[0] + channel_delta[2]) / 2) - channel_delta[1]
    return {
        "rgb_mean_delta": {
            "red": _round(channel_delta[0]),
            "green": _round(channel_delta[1]),
            "blue": _round(channel_delta[2]),
        },
        "temperature_shift": _round(temperature_shift),
        "tint_shift": _round(tint_shift),
    }


def _saturation_features(inputs: np.ndarray, outputs: np.ndarray) -> dict[str, Any]:
    input_hsv = _rgb_to_hsv(inputs)
    output_hsv = _rgb_to_hsv(outputs)
    chroma_mask = input_hsv[:, 1] > 0.05
    if not np.any(chroma_mask):
        chroma_mask = np.ones(input_hsv.shape[0], dtype=bool)
    sat_delta = output_hsv[chroma_mask, 1] - input_hsv[chroma_mask, 1]
    return {
        "mean_delta": _round(float(np.mean(sat_delta))),
        "p10_delta": _round(float(np.percentile(sat_delta, 10))),
        "p90_delta": _round(float(np.percentile(sat_delta, 90))),
        "output_mean": _round(float(np.mean(output_hsv[chroma_mask, 1]))),
    }


def _probe_features(lut: CubeLut) -> dict[str, Any]:
    probes = {
        "red": (1.0, 0.05, 0.05),
        "orange": (1.0, 0.45, 0.05),
        "yellow": (1.0, 1.0, 0.05),
        "green": (0.05, 1.0, 0.05),
        "aqua": (0.05, 1.0, 1.0),
        "blue": (0.05, 0.05, 1.0),
        "purple": (0.45, 0.05, 1.0),
        "magenta": (1.0, 0.05, 1.0),
    }
    inputs = np.asarray(list(probes.values()), dtype=np.float32)
    outputs = apply_lut(lut, inputs)
    input_hsv = _rgb_to_hsv(inputs)
    output_hsv = _rgb_to_hsv(outputs)
    input_luma = _luma(inputs)
    output_luma = _luma(outputs)

    result: dict[str, Any] = {}
    for index, name in enumerate(probes):
        result[name] = {
            "hue_shift_degrees": _round(_hue_delta_degrees(float(input_hsv[index, 0]), float(output_hsv[index, 0])), 2),
            "saturation_delta": _round(output_hsv[index, 1] - input_hsv[index, 1]),
            "luminance_delta": _round(output_luma[index] - input_luma[index]),
        }
    return result


def _split_tone_features(lut: CubeLut) -> dict[str, Any]:
    shadows = np.asarray([[0.18, 0.18, 0.18]], dtype=np.float32)
    highlights = np.asarray([[0.82, 0.82, 0.82]], dtype=np.float32)
    shadow_delta = apply_lut(lut, shadows)[0] - shadows[0]
    highlight_delta = apply_lut(lut, highlights)[0] - highlights[0]
    return {
        "shadow_rgb_bias": {"red": _round(shadow_delta[0]), "green": _round(shadow_delta[1]), "blue": _round(shadow_delta[2])},
        "highlight_rgb_bias": {
            "red": _round(highlight_delta[0]),
            "green": _round(highlight_delta[1]),
            "blue": _round(highlight_delta[2]),
        },
        "shadow_cool_bias": _round(shadow_delta[2] - shadow_delta[0]),
        "highlight_warm_bias": _round(highlight_delta[0] - highlight_delta[2]),
    }


def _derive_tags(features: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    temperature_shift = features["color_balance"]["temperature_shift"]
    saturation_delta = features["saturation"]["mean_delta"]
    contrast_delta = features["tone"]["contrast_delta"]
    shadow_cool = features["split_tone"]["shadow_cool_bias"]
    highlight_warm = features["split_tone"]["highlight_warm_bias"]
    output_saturation = features["saturation"]["output_mean"]

    if temperature_shift <= -0.035:
        tags.append("cool")
    elif temperature_shift >= 0.035:
        tags.append("warm")

    if saturation_delta <= -0.06:
        tags.append("muted")
    elif saturation_delta >= 0.06:
        tags.append("vibrant")

    if output_saturation <= 0.12 and saturation_delta < -0.2:
        tags.append("monochrome_like")

    if contrast_delta <= -0.05:
        tags.append("soft_contrast")
    elif contrast_delta >= 0.05:
        tags.append("high_contrast")

    if shadow_cool > 0.03 and highlight_warm > 0.03:
        tags.append("cinematic_split_tone")

    return tags or ["balanced"]


def extract_lut_style_profile(
    lut: CubeLut,
    *,
    concept: str | None,
    metadata: LutProfileMetadata,
    profile_id: str,
) -> LutStyleProfile:
    grid_inputs = _input_grid(lut.size).reshape((-1, 3))
    grid_outputs = lut.table.reshape((-1, 3))
    features: dict[str, Any] = {
        "tone": _tone_features(lut),
        "color_balance": _balance_features(grid_inputs, grid_outputs),
        "saturation": _saturation_features(grid_inputs, grid_outputs),
        "color_probes": _probe_features(lut),
        "split_tone": _split_tone_features(lut),
        "privacy": {
            "stores_lookup_table": False,
            "stores_original_file": False,
            "non_invertible_summary": True,
        },
    }

    return LutStyleProfile(
        id=profile_id,
        concept=concept.strip() if concept and concept.strip() else None,
        title=lut.title,
        cubeSize=lut.size,
        metadata=metadata,
        derivedTags=_derive_tags(features),
        features=features,
    )


def _profile_path(profile: LutStyleProfile, reference_root: Path) -> Path:
    return reference_root / "luts" / "profiles" / f"{profile.id}.json"


def _write_profile(profile: LutStyleProfile, reference_root: Path) -> Path:
    path = _profile_path(profile, reference_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    return path


def ingest_lut_bytes(
    content: bytes,
    *,
    filename: str,
    concept: str | None = None,
    source_url: str | None = None,
    license_name: str | None = None,
    status: str = "unknown",
    source_type: str = "user_import",
    downloaded_at: str | None = None,
    imported_at: str | None = None,
    reference_root: Path | None = None,
) -> LutIngestResponse:
    if not content:
        raise LutAnalysisError("Uploaded LUT file is empty")
    if len(content) > MAX_LUT_BYTES:
        raise LutAnalysisError(f"LUT file is larger than the {MAX_LUT_BYTES // (1024 * 1024)}MB safety limit")
    if Path(filename).suffix.lower() != ".cube":
        raise LutAnalysisError("Only .cube LUT files are supported")

    root = reference_root or _reference_root()
    sha256 = hashlib.sha256(content).hexdigest()
    text = _decode_cube_text(content)
    lut = parse_cube_lut(text)

    profile_id = f"{_safe_stem(filename)}-{sha256[:12]}"
    metadata = LutProfileMetadata(
        sourceUrl=source_url,
        license=license_name,
        status=status,  # type: ignore[arg-type]
        sourceType=source_type,  # type: ignore[arg-type]
        downloadedAt=downloaded_at,
        importedAt=imported_at or (None if downloaded_at else _utc_now()),
        sha256=sha256,
        originalFilename=Path(filename).name,
        originalDeleted=True,
    )
    profile = extract_lut_style_profile(lut, concept=concept, metadata=metadata, profile_id=profile_id)
    profile_path = _write_profile(profile, root)
    return LutIngestResponse(profilePath=_relative_path(profile_path, root), profile=profile)


def load_lut_source_registry(reference_root: Path | None = None) -> LutSourceRegistry:
    root = reference_root or _reference_root()
    path = root / "luts" / "source_registry.json"
    if not path.exists():
        return LutSourceRegistry()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise LutAnalysisError(f"Cannot read LUT source registry: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LutAnalysisError(f"Invalid LUT source registry JSON: {exc}") from exc
    try:
        return LutSourceRegistry.model_validate(payload)
    except ValidationError as exc:
        raise LutAnalysisError(f"Invalid LUT source registry: {exc}") from exc


def _matching_source(source_url: str, registry: LutSourceRegistry) -> LutSourceEntry | None:
    matches: list[tuple[int, LutSourceEntry]] = []
    for source in registry.sources:
        for prefix in source.urlPrefixes:
            if source_url.startswith(prefix):
                matches.append((len(prefix), source))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[0][1]


def assert_url_ingest_allowed(source_url: str, registry: LutSourceRegistry) -> LutSourceEntry:
    source = _matching_source(source_url, registry)
    if source is None:
        raise LutSourcePolicyError("Source URL is not in the allowlisted LUT source registry")
    if source.status != "allow":
        raise LutSourcePolicyError(f"Source {source.id} is marked {source.status}, not allow")
    if not source.directDownloadAllowed:
        raise LutSourcePolicyError(f"Source {source.id} does not allow direct automatic downloads")
    return source


def download_lut_url(source_url: str) -> bytes:
    request = urllib.request.Request(
        source_url,
        headers={"User-Agent": "TonePilotLocal/0.1 LUT-style-analyzer"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_LUT_BYTES:
                raise LutAnalysisError(f"Downloaded LUT exceeds the {MAX_LUT_BYTES // (1024 * 1024)}MB safety limit")
            chunks.append(chunk)
    return b"".join(chunks)


def ingest_lut_url(
    source_url: str,
    *,
    concept: str | None = None,
    reference_root: Path | None = None,
    downloader: DownloadFn | None = None,
) -> LutIngestResponse:
    root = reference_root or _reference_root()
    registry = load_lut_source_registry(root)
    source = assert_url_ingest_allowed(source_url, registry)
    content = (downloader or download_lut_url)(source_url)
    filename = Path(source_url.split("?", 1)[0]).name or f"{source.id}.cube"
    return ingest_lut_bytes(
        content,
        filename=filename,
        concept=concept,
        source_url=source_url,
        license_name=source.license,
        status=source.status,
        source_type=source.sourceType,
        downloaded_at=_utc_now(),
        imported_at=None,
        reference_root=root,
    )


def load_lut_style_profiles(reference_root: Path | None = None) -> LutProfileListResponse:
    root = reference_root or _reference_root()
    profiles_dir = root / "luts" / "profiles"
    if not profiles_dir.exists():
        return LutProfileListResponse(count=0, items=[])

    items: list[LutStyleProfile] = []
    for profile_path in sorted(profiles_dir.glob("*.json")):
        try:
            payload = json.loads(profile_path.read_text(encoding="utf-8"))
            items.append(LutStyleProfile.model_validate(payload))
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise LutAnalysisError(f"Invalid LUT style profile {profile_path.name}: {exc}") from exc
    return LutProfileListResponse(count=len(items), items=items)
