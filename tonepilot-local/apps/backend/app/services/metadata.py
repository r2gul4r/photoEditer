from fractions import Fraction
from pathlib import Path
from typing import Any

from PIL import ExifTags, Image

from app.models.schemas import ImageMetadata


EXIF_NAMES = {value: key for key, value in ExifTags.TAGS.items()}


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


def _aperture(value: Any) -> str | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except Exception:
        return _ratio_to_string(value)
    return f"f/{numeric:.1f}"


def read_metadata(path: Path) -> ImageMetadata:
    try:
        with Image.open(path) as image:
            exif = image.getexif()
            if not exif:
                return ImageMetadata()
            get = lambda name: exif.get(EXIF_NAMES.get(name))  # noqa: E731
            make = get("Make")
            model = get("Model")
            camera = " ".join(str(part).strip() for part in [make, model] if part)
            return ImageMetadata(
                camera=camera or None,
                lens=str(get("LensModel")) if get("LensModel") else None,
                iso=int(get("ISOSpeedRatings")) if get("ISOSpeedRatings") else None,
                shutter=_ratio_to_string(get("ExposureTime")),
                aperture=_aperture(get("FNumber")),
                focal_length=_ratio_to_string(get("FocalLength")),
                created_at=str(get("DateTimeOriginal") or get("DateTime")) if (get("DateTimeOriginal") or get("DateTime")) else None,
            )
    except Exception:
        return ImageMetadata()

