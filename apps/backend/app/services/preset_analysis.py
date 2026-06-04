from __future__ import annotations

import hashlib
import html
import io
import json
import re
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.models.schemas import (
    PresetIngestResponse,
    PresetProfileListResponse,
    PresetSourceEntry,
    PresetSourceRegistry,
    PresetStyleProfile,
)


class PresetAnalysisError(RuntimeError):
    pass


class PresetSourcePolicyError(PresetAnalysisError):
    pass


SLIDER_FIELDS = {
    "exposure": ("Exposure2012", "Exposure"),
    "contrast": ("Contrast2012", "Contrast"),
    "highlights": ("Highlights2012", "Highlights"),
    "shadows": ("Shadows2012", "Shadows"),
    "whites": ("Whites2012", "Whites"),
    "blacks": ("Blacks2012", "Blacks"),
    "temperature": ("Temperature",),
    "tint": ("Tint",),
    "vibrance": ("Vibrance",),
    "saturation": ("Saturation",),
    "clarity": ("Clarity2012", "Clarity"),
    "texture": ("Texture",),
    "dehaze": ("Dehaze",),
}

HSL_COLORS = {
    "red": "Red",
    "orange": "Orange",
    "yellow": "Yellow",
    "green": "Green",
    "aqua": "Aqua",
    "blue": "Blue",
    "purple": "Purple",
    "magenta": "Magenta",
}

GROUP_HINT_KEYWORDS = {
    "wedding": ("wedding", "bridal", "marriage", "boho wedding"),
    "beauty": ("beauty", "skin", "skintone", "portrait", "newborn"),
    "monochrome": ("black white", "black and white", "bw", "b w", "mono", "noir"),
    "teal_orange": ("teal orange", "teal", "orange city", "blockbuster"),
    "cool": ("cool", "cold", "blue", "night", "winter", "snow"),
    "warm": ("warm", "sunset", "golden", "summer", "cozy"),
    "film": ("film", "vintage", "retro", "kodak", "fuji", "portra", "35mm"),
    "pastel": ("pastel", "airy", "light airy", "soft", "dreamy"),
    "vibrant": ("vibrant", "pop", "colorful", "sport", "travel"),
    "clean": ("clean", "natural", "product", "real estate", "interior"),
    "cinematic": ("cinematic", "moody", "urban", "city", "dramatic"),
}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _reference_root() -> Path:
    return _project_root() / "reference"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug[:80] or "preset"


def _num(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().strip('"').replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _normalize_text(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").casefold()).strip()


def _source_key(url: str | None) -> str:
    if not url:
        return "user_import"
    parts = url.split("/")
    if len(parts) >= 5:
        return "/".join(parts[2:5])
    return url


def _preset_root(reference_root: Path) -> Path:
    return reference_root / "presets"


def _profiles_dir(reference_root: Path) -> Path:
    return _preset_root(reference_root) / "profiles"


def _registry_path(reference_root: Path) -> Path:
    return _preset_root(reference_root) / "source_registry.json"


def _profile_path(profile: PresetStyleProfile, reference_root: Path) -> Path:
    return _profiles_dir(reference_root) / f"{profile.id}.json"


def _default_registry() -> PresetSourceRegistry:
    return PresetSourceRegistry(
        sources=[
            PresetSourceEntry(
                id="user-local-preset-import",
                name="User Local Preset Import",
                status="allow",
                sourceType="user_import",
                license="user-provided",
                directDownloadAllowed=False,
                notes="For presets manually provided by the user.",
            ),
            PresetSourceEntry(
                id="thepresetsroom-free-presets",
                name="The Presets Room Free Presets",
                status="allow",
                sourceType="allowed_public_preset",
                urlPrefixes=[
                    "https://thepresetsroom.com/free-lightroom-presets/",
                    "https://thepresetsroom.b-cdn.net/free-download/",
                ],
                license="free public download; original files are not redistributed",
                directDownloadAllowed=True,
                notes="Used only for low-dimensional preset behavior analysis.",
            ),
            PresetSourceEntry(
                id="editingfree-youtube-free-presets",
                name="Editingfree YouTube Free Presets",
                status="allow",
                sourceType="allowed_public_preset",
                urlPrefixes=[
                    "https://editingfree.com/",
                    "https://docs.google.com/uc?export=download",
                    "https://drive.usercontent.google.com/download",
                ],
                license="free public download; original files are not redistributed",
                directDownloadAllowed=True,
                notes="YouTube-linked creator site used only for low-dimensional preset behavior analysis.",
            ),
            PresetSourceEntry(
                id="mackytravel-youtube-free-presets",
                name="MackyTravel YouTube Free Presets",
                status="unknown",
                sourceType="allowed_public_preset",
                urlPrefixes=[
                    "https://mackytravel.com/",
                ],
                license="free public download pages; AES ZIP originals not ingested without explicit tool support",
                directDownloadAllowed=False,
                notes="Official YouTube-linked creator source candidate; encrypted ZIPs are recorded as skipped unless a compatible extractor is available.",
            ),
        ]
    )


def load_preset_source_registry(reference_root: Path | None = None) -> PresetSourceRegistry:
    root = reference_root or _reference_root()
    path = _registry_path(root)
    if not path.exists():
        return _default_registry()
    try:
        return PresetSourceRegistry.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise PresetAnalysisError(f"Invalid preset source registry: {path}") from exc


def save_default_preset_source_registry(reference_root: Path | None = None) -> PresetSourceRegistry:
    root = reference_root or _reference_root()
    registry = _default_registry()
    path = _registry_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(registry.model_dump_json(indent=2), encoding="utf-8")
    return registry


def _policy_for_url(url: str | None, registry: PresetSourceRegistry) -> PresetSourceEntry | None:
    if not url:
        return next((source for source in registry.sources if source.sourceType == "user_import"), None)
    for source in registry.sources:
        if source.status == "allow" and any(url.startswith(prefix) for prefix in source.urlPrefixes):
            return source
    return None


def _extract_crs_properties(text: str) -> dict[str, str]:
    props: dict[str, str] = {}
    for key, value in re.findall(r"\bcrs:([A-Za-z0-9_]+)\s*=\s*\"([^\"]*)\"", text):
        props[key] = html.unescape(value)
    for key, value in re.findall(r"<crs:([A-Za-z0-9_]+)>(.*?)</crs:\1>", text, flags=re.DOTALL):
        clean = re.sub(r"<[^>]+>", " ", value)
        clean = re.sub(r"\s+", " ", html.unescape(clean)).strip()
        if clean:
            props.setdefault(key, clean)
    return props


def _extract_lua_properties(text: str) -> dict[str, str]:
    props: dict[str, str] = {}
    for key, value in re.findall(r"\[\"([A-Za-z0-9_]+)\"\]\s*=\s*\"?([^\",\n}]+)\"?", text):
        props[key] = value.strip()
    for key, value in re.findall(r"\b([A-Za-z0-9_]+)\s*=\s*\"?([^\",\n}]+)\"?", text):
        props.setdefault(key, value.strip())
    return props


def _extract_arrays(text: str, tag: str) -> list[str]:
    match = re.search(rf"<crs:{tag}>(.*?)</crs:{tag}>", text, flags=re.DOTALL)
    if not match:
        return []
    return [html.unescape(value.strip()) for value in re.findall(r"<rdf:li[^>]*>(.*?)</rdf:li>", match.group(1), flags=re.DOTALL)]


def _extract_sliders(props: dict[str, str]) -> dict[str, float]:
    sliders: dict[str, float] = {}
    for name, keys in SLIDER_FIELDS.items():
        for key in keys:
            number = _num(props.get(key))
            if number is None:
                continue
            if name == "temperature" and abs(number) > 2000:
                number = max(-2000.0, min(2000.0, number - 5500.0))
            sliders[name] = round(number, 3)
            break
    return sliders


def _extract_hsl(props: dict[str, str]) -> dict[str, dict[str, float]]:
    hsl: dict[str, dict[str, float]] = {}
    for color, suffix in HSL_COLORS.items():
        values: dict[str, float] = {}
        for channel, prefix in (("hue", "HueAdjustment"), ("saturation", "SaturationAdjustment"), ("luminance", "LuminanceAdjustment")):
            number = _num(props.get(f"{prefix}{suffix}"))
            if number is not None:
                values[channel] = round(number, 3)
        if values:
            hsl[color] = values
    return hsl


def _extract_color_grading(props: dict[str, str]) -> dict[str, dict[str, float]]:
    grading: dict[str, dict[str, float]] = {}
    for zone, prefix in (
        ("shadows", "ColorGradeShadow"),
        ("midtones", "ColorGradeMidtone"),
        ("highlights", "ColorGradeHighlight"),
        ("global", "ColorGradeGlobal"),
    ):
        values: dict[str, float] = {}
        for channel in ("Hue", "Sat", "Lum"):
            number = _num(props.get(f"{prefix}{channel}"))
            if number is not None:
                values[channel.casefold()] = round(number, 3)
        if values:
            grading[zone] = values
    for zone, prefix in (("shadows", "SplitToningShadow"), ("highlights", "SplitToningHighlight")):
        values = grading.setdefault(zone, {})
        for channel in ("Hue", "Saturation"):
            number = _num(props.get(f"{prefix}{channel}"))
            if number is not None:
                values[channel.casefold()] = round(number, 3)
        if not values:
            grading.pop(zone, None)
    return grading


def _extract_calibration(props: dict[str, str]) -> dict[str, float | str]:
    calibration: dict[str, float | str] = {}
    for key in ("RedHue", "RedSaturation", "GreenHue", "GreenSaturation", "BlueHue", "BlueSaturation", "ShadowTint"):
        number = _num(props.get(key))
        if number is not None:
            calibration[key] = round(number, 3)
    for key in ("CameraProfile", "LookName", "ProcessVersion", "ProfileName"):
        if props.get(key):
            calibration[key] = props[key]
    return calibration


def _derive_tags(title: str, concept: str | None, sliders: dict[str, float], hsl: dict[str, dict[str, float]]) -> list[str]:
    text = _normalize_text(f"{title} {concept or ''}")
    tags: list[str] = []
    for tag, keywords in GROUP_HINT_KEYWORDS.items():
        if any(_normalize_text(keyword) in text for keyword in keywords):
            tags.append(tag)

    temperature = sliders.get("temperature", 0)
    contrast = sliders.get("contrast", 0)
    saturation = sliders.get("saturation", 0) + sliders.get("vibrance", 0)
    hsl_sat = sum(values.get("saturation", 0) for values in hsl.values())

    if temperature > 250 and "warm" not in tags:
        tags.append("warm")
    if temperature < -250 and "cool" not in tags:
        tags.append("cool")
    if contrast > 18:
        tags.append("high_contrast")
    if contrast < -12:
        tags.append("soft_contrast")
    if saturation + hsl_sat / 8 > 18 and "vibrant" not in tags:
        tags.append("vibrant")
    if saturation + hsl_sat / 8 < -14:
        tags.append("muted")
    if sliders.get("saturation", 0) < -35 or "monochrome" in tags:
        if "monochrome" not in tags:
            tags.append("monochrome")
    return tags


def analyze_preset_text(text: str, *, filename: str, concept: str | None = None) -> dict[str, Any]:
    lower = filename.casefold()
    preset_format = "lrtemplate" if lower.endswith(".lrtemplate") else "xmp"
    props = _extract_lua_properties(text) if preset_format == "lrtemplate" else _extract_crs_properties(text)
    title = props.get("Name") or props.get("InternalName") or Path(filename).stem
    sliders = _extract_sliders(props)
    hsl = _extract_hsl(props)
    grading = _extract_color_grading(props)
    calibration = _extract_calibration(props)
    tone_curve = {
        "rgb": _extract_arrays(text, "ToneCurvePV2012") or _extract_arrays(text, "ToneCurve"),
        "red": _extract_arrays(text, "ToneCurvePV2012Red"),
        "green": _extract_arrays(text, "ToneCurvePV2012Green"),
        "blue": _extract_arrays(text, "ToneCurvePV2012Blue"),
    }
    tone_curve = {key: value for key, value in tone_curve.items() if value}
    tags = _derive_tags(title, concept, sliders, hsl)
    return {
        "title": title,
        "format": preset_format,
        "derivedTags": tags,
        "features": {
            "sliderAdjustments": sliders,
            "hslAdjustments": hsl,
            "colorGrading": grading,
            "calibration": calibration,
            "toneCurve": tone_curve,
            "includedKeys": sorted(props.keys()),
        },
    }


def ingest_preset_bytes(
    content: bytes,
    *,
    filename: str,
    concept: str | None = None,
    source_url: str | None = None,
    download_url: str | None = None,
    license_name: str | None = None,
    source_type: str | None = None,
    downloaded_at: str | None = None,
    reference_root: Path | None = None,
) -> PresetIngestResponse:
    root = reference_root or _reference_root()
    suffix = Path(filename).suffix.casefold()
    if suffix not in {".xmp", ".lrtemplate"}:
        raise PresetAnalysisError(f"Unsupported Lightroom preset format: {filename}")

    registry = load_preset_source_registry(root)
    policy = _policy_for_url(source_url or download_url, registry)
    if policy is None:
        raise PresetSourcePolicyError(f"Preset source is not allowlisted: {source_url or download_url or filename}")

    sha = hashlib.sha256(content).hexdigest()
    text = content.decode("utf-8-sig", errors="ignore")
    analyzed = analyze_preset_text(text, filename=filename, concept=concept)
    title = str(analyzed["title"])
    profile = PresetStyleProfile(
        id=f"{_slug(title)}-{sha[:12]}",
        concept=concept,
        title=title,
        format=analyzed["format"],
        metadata={
            "sourceUrl": source_url,
            "downloadUrl": download_url,
            "license": license_name or policy.license,
            "status": policy.status,
            "sourceType": source_type or policy.sourceType,
            "downloadedAt": downloaded_at,
            "importedAt": None if downloaded_at else _now_iso(),
            "sha256": sha,
            "originalFilename": filename,
            "originalDeleted": True,
        },
        derivedTags=analyzed["derivedTags"],
        features=analyzed["features"],
    )
    path = _profile_path(profile, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    return PresetIngestResponse(profilePath=str(path.relative_to(root)).replace("\\", "/"), profile=profile)


def ingest_preset_archive_bytes(
    content: bytes,
    *,
    filename: str,
    concept: str | None = None,
    source_url: str | None = None,
    download_url: str | None = None,
    license_name: str | None = None,
    source_type: str | None = None,
    downloaded_at: str | None = None,
    reference_root: Path | None = None,
    max_profiles: int | None = None,
    formats: set[str] | None = None,
) -> list[PresetIngestResponse]:
    if not zipfile.is_zipfile(io.BytesIO(content)):
        return [
            ingest_preset_bytes(
                content,
                filename=filename,
                concept=concept,
                source_url=source_url,
                download_url=download_url,
                license_name=license_name,
                source_type=source_type,
                downloaded_at=downloaded_at,
                reference_root=reference_root,
            )
        ]

    responses: list[PresetIngestResponse] = []
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        allowed_suffixes = formats or {".xmp", ".lrtemplate"}
        names = [
            name
            for name in archive.namelist()
            if not name.startswith("__MACOSX/")
            and not Path(name).name.startswith(".")
            and Path(name).suffix.casefold() in allowed_suffixes
        ]
        names.sort(key=lambda name: (Path(name).suffix.casefold() != ".xmp", name.casefold()))
        for name in names:
            if max_profiles is not None and len(responses) >= max_profiles:
                break
            responses.append(
                ingest_preset_bytes(
                    archive.read(name),
                    filename=Path(name).name,
                    concept=concept,
                    source_url=source_url,
                    download_url=download_url,
                    license_name=license_name,
                    source_type=source_type,
                    downloaded_at=downloaded_at,
                    reference_root=reference_root,
                )
            )
    if not responses:
        raise PresetAnalysisError(f"No .xmp or .lrtemplate presets found in archive: {filename}")
    return responses


def ingest_preset_url(
    source_url: str,
    *,
    concept: str | None = None,
    reference_root: Path | None = None,
    downloader: Callable[[str], bytes],
) -> list[PresetIngestResponse]:
    root = reference_root or _reference_root()
    registry = load_preset_source_registry(root)
    policy = _policy_for_url(source_url, registry)
    if policy is None or not policy.directDownloadAllowed:
        raise PresetSourcePolicyError(f"Preset URL is not in the allowlisted direct-download sources: {source_url}")
    content = downloader(source_url)
    return ingest_preset_archive_bytes(
        content,
        filename=Path(source_url.split("#")[0]).name or "download.zip",
        concept=concept,
        source_url=source_url,
        download_url=source_url,
        license_name=policy.license,
        source_type=policy.sourceType,
        downloaded_at=_now_iso(),
        reference_root=root,
    )


def load_preset_style_profiles(reference_root: Path | None = None) -> PresetProfileListResponse:
    root = reference_root or _reference_root()
    profiles_dir = _profiles_dir(root)
    if not profiles_dir.exists():
        return PresetProfileListResponse(count=0, items=[])

    items: list[PresetStyleProfile] = []
    for profile_path in sorted(profiles_dir.glob("*.json")):
        try:
            payload = json.loads(profile_path.read_text(encoding="utf-8"))
            items.append(PresetStyleProfile.model_validate(payload))
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise PresetAnalysisError(f"Invalid preset style profile: {profile_path}") from exc
    return PresetProfileListResponse(count=len(items), items=items)
