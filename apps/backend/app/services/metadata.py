from fractions import Fraction
from pathlib import Path
from typing import Any

from PIL import ExifTags, Image

from app.models.schemas import ImageMetadata, MetadataField


EXIF_NAMES = {value: key for key, value in ExifTags.TAGS.items()}
GPS_NAMES = {value: key for key, value in ExifTags.GPSTAGS.items()}

SUMMARY_EXIFREAD_KEYS = {
    "make": ("Image Make", "EXIF Make"),
    "model": ("Image Model", "EXIF Model"),
    "lens": ("EXIF LensModel", "EXIF LensMake", "Image LensModel"),
    "iso": ("EXIF ISOSpeedRatings", "EXIF PhotographicSensitivity"),
    "shutter": ("EXIF ExposureTime",),
    "aperture": ("EXIF FNumber",),
    "focal_length": ("EXIF FocalLength",),
    "created_at": ("EXIF DateTimeOriginal", "Image DateTime", "EXIF DateTimeDigitized"),
}


def _ratio_to_string(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if isinstance(value, tuple) and len(value) == 2:
            return str(Fraction(value[0], value[1]))
        if hasattr(value, "numerator") and hasattr(value, "denominator"):
            return str(Fraction(value.numerator, value.denominator))
        return str(value)
    except Exception:
        return None


def _metadata_value_to_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        try:
            text = value.decode("utf-8", errors="replace").strip("\x00")
        except Exception:
            text = value.hex()
    elif isinstance(value, dict):
        parts = []
        for key, nested in value.items():
            name = GPS_NAMES.get(key, str(key)) if isinstance(key, int) else str(key)
            nested_value = _metadata_value_to_string(nested)
            if nested_value is not None:
                parts.append(f"{name}: {nested_value}")
        text = ", ".join(parts)
    elif isinstance(value, (list, tuple)):
        text = ", ".join(str(item) for item in value)
    else:
        text = str(value)
    text = " ".join(text.split())
    if not text:
        return None
    return text if len(text) <= 600 else f"{text[:597]}..."


def _pillow_fields(path: Path) -> tuple[dict[str, Any], list[MetadataField]]:
    try:
        with Image.open(path) as image:
            exif = image.getexif()
            if not exif:
                return {}, []
            named = {ExifTags.TAGS.get(tag, str(tag)): value for tag, value in exif.items()}
            fields = []
            for key, value in sorted(named.items(), key=lambda item: str(item[0])):
                text = _metadata_value_to_string(value)
                if text is not None:
                    fields.append(MetadataField(key=str(key), value=text, source="pillow"))
            return named, fields
    except Exception:
        return {}, []


def _exifread_fields(path: Path) -> dict[str, str]:
    try:
        import exifread  # type: ignore
    except Exception:
        return {}

    try:
        with path.open("rb") as handle:
            tags = exifread.process_file(handle, details=False, strict=False)
    except Exception:
        return {}

    fields: dict[str, str] = {}
    for key, value in sorted(tags.items(), key=lambda item: item[0]):
        if key == "JPEGThumbnail":
            continue
        text = _metadata_value_to_string(value)
        if text is not None:
            fields[str(key)] = text
    return fields


def _first_exifread(exif_fields: dict[str, str], names: tuple[str, ...]) -> str | None:
    for name in names:
        value = exif_fields.get(name)
        if value:
            return value
    return None


def _aperture(value: Any) -> str | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except Exception:
        return _ratio_to_string(value)
    return f"f/{numeric:.1f}"


def read_metadata(path: Path) -> ImageMetadata:
    pillow_exif, pillow_fields = _pillow_fields(path)
    exifread_values = _exifread_fields(path)
    exifread_metadata_fields = [
        MetadataField(key=key, value=value, source="exifread") for key, value in exifread_values.items()
    ]

    get = lambda name: pillow_exif.get(name)  # noqa: E731
    make = get("Make") or _first_exifread(exifread_values, SUMMARY_EXIFREAD_KEYS["make"])
    model = get("Model") or _first_exifread(exifread_values, SUMMARY_EXIFREAD_KEYS["model"])
    camera = " ".join(str(part).strip() for part in [make, model] if part)
    iso = get("ISOSpeedRatings") or _first_exifread(exifread_values, SUMMARY_EXIFREAD_KEYS["iso"])
    try:
        iso_value = int(str(iso).split(",")[0].strip()) if iso is not None else None
    except Exception:
        iso_value = None

    return ImageMetadata(
        camera=camera or None,
        lens=(
            str(get("LensModel"))
            if get("LensModel")
            else _first_exifread(exifread_values, SUMMARY_EXIFREAD_KEYS["lens"])
        ),
        iso=iso_value,
        shutter=_ratio_to_string(get("ExposureTime")) or _first_exifread(exifread_values, SUMMARY_EXIFREAD_KEYS["shutter"]),
        aperture=_aperture(get("FNumber")) or _first_exifread(exifread_values, SUMMARY_EXIFREAD_KEYS["aperture"]),
        focal_length=_ratio_to_string(get("FocalLength")) or _first_exifread(exifread_values, SUMMARY_EXIFREAD_KEYS["focal_length"]),
        created_at=(
            str(get("DateTimeOriginal") or get("DateTime"))
            if (get("DateTimeOriginal") or get("DateTime"))
            else _first_exifread(exifread_values, SUMMARY_EXIFREAD_KEYS["created_at"])
        ),
        fields=pillow_fields + exifread_metadata_fields,
    )

