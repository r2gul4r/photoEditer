from pathlib import Path

from PIL import Image, ImageOps


SUPPORTED_EXTENSIONS = {
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".png": "png",
    ".tif": "tiff",
    ".tiff": "tiff",
}

RAW_EXTENSIONS = {
    ".arw",
    ".cr2",
    ".cr3",
    ".dng",
    ".nef",
    ".orf",
    ".raf",
    ".rw2",
}


def infer_file_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in SUPPORTED_EXTENSIONS:
        return SUPPORTED_EXTENSIONS[suffix]
    if suffix in RAW_EXTENSIONS:
        return "raw"
    return suffix.removeprefix(".") or "unknown"


def load_rgb_image(path: Path) -> Image.Image:
    image = Image.open(path)
    image = ImageOps.exif_transpose(image)
    return image.convert("RGB")


def downscale(image: Image.Image, max_side: int) -> Image.Image:
    if max(image.size) <= max_side:
        return image.copy()
    copy = image.copy()
    copy.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return copy

