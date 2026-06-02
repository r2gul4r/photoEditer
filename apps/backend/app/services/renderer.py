import numpy as np
from PIL import Image, ImageFilter

from app.config import settings
from app.models.schemas import CorrectionAdjustments
from app.utils.histograms import luma_from_rgb, saturation_from_rgb
from app.utils.image_io import downscale


HUE_RANGES = {
    "red": ((345, 360), (0, 15)),
    "orange": ((15, 45),),
    "yellow": ((45, 75),),
    "green": ((75, 165),),
    "aqua": ((165, 200),),
    "blue": ((200, 255),),
    "purple": ((255, 290),),
    "magenta": ((290, 345),),
}


def _clip(rgb: np.ndarray) -> np.ndarray:
    return np.clip(rgb, 0.0, 1.0)


def _rgb_to_hsv(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    maxc = np.max(rgb, axis=-1)
    minc = np.min(rgb, axis=-1)
    delta = maxc - minc

    hue = np.zeros_like(maxc)
    mask = delta > 1e-6
    hue = np.where(mask & (maxc == r), ((g - b) / np.maximum(delta, 1e-6)) % 6, hue)
    hue = np.where(mask & (maxc == g), ((b - r) / np.maximum(delta, 1e-6)) + 2, hue)
    hue = np.where(mask & (maxc == b), ((r - g) / np.maximum(delta, 1e-6)) + 4, hue)
    hue = hue * 60
    sat = np.where(maxc <= 1e-6, 0.0, delta / maxc)
    return hue, sat, maxc


def _hsv_to_rgb(hue: np.ndarray, sat: np.ndarray, value: np.ndarray) -> np.ndarray:
    h = (hue % 360) / 60
    c = value * sat
    x = c * (1 - np.abs((h % 2) - 1))
    m = value - c

    zeros = np.zeros_like(h)
    rp, gp, bp = zeros.copy(), zeros.copy(), zeros.copy()

    conditions = [
        (0 <= h) & (h < 1),
        (1 <= h) & (h < 2),
        (2 <= h) & (h < 3),
        (3 <= h) & (h < 4),
        (4 <= h) & (h < 5),
        (5 <= h) & (h < 6),
    ]
    choices = [(c, x, zeros), (x, c, zeros), (zeros, c, x), (zeros, x, c), (x, zeros, c), (c, zeros, x)]
    for condition, (rc, gc, bc) in zip(conditions, choices):
        rp = np.where(condition, rc, rp)
        gp = np.where(condition, gc, gp)
        bp = np.where(condition, bc, bp)

    return np.stack([rp + m, gp + m, bp + m], axis=-1)


def _apply_temperature_tint(rgb: np.ndarray, temperature: float, tint: float) -> np.ndarray:
    temp = temperature / 2000.0
    tint_norm = tint / 50.0
    rgb[..., 0] += temp * 0.09
    rgb[..., 2] -= temp * 0.09
    rgb[..., 1] += tint_norm * 0.045
    rgb[..., 0] -= tint_norm * 0.018
    rgb[..., 2] -= tint_norm * 0.018
    return _clip(rgb)


def _apply_highlights_shadows(rgb: np.ndarray, adjustments: CorrectionAdjustments) -> np.ndarray:
    luma = luma_from_rgb(rgb)
    highlight_mask = np.clip((luma - 0.55) / 0.45, 0.0, 1.0)[..., None]
    shadow_mask = np.clip((0.55 - luma) / 0.55, 0.0, 1.0)[..., None]

    rgb += highlight_mask * (adjustments.highlights / 100.0) * 0.22
    rgb += shadow_mask * (adjustments.shadows / 100.0) * 0.22
    rgb += np.clip((luma - 0.7) / 0.3, 0.0, 1.0)[..., None] * (adjustments.whites / 100.0) * 0.16
    rgb += np.clip((0.3 - luma) / 0.3, 0.0, 1.0)[..., None] * (adjustments.blacks / 100.0) * 0.16
    return _clip(rgb)


def _apply_saturation(rgb: np.ndarray, vibrance: float, saturation: float) -> np.ndarray:
    luma = luma_from_rgb(rgb)[..., None]
    current_sat = saturation_from_rgb(rgb)[..., None]
    sat_factor = 1 + saturation / 100.0
    vibrance_factor = 1 + (vibrance / 100.0) * (1 - current_sat)
    return _clip(luma + (rgb - luma) * sat_factor * vibrance_factor)


def _apply_local_contrast(rgb: np.ndarray, amount: float) -> np.ndarray:
    if abs(amount) < 0.1:
        return rgb
    image = Image.fromarray((_clip(rgb) * 255).astype(np.uint8))
    blurred = np.asarray(image.filter(ImageFilter.GaussianBlur(radius=3))).astype(np.float32) / 255.0
    return _clip(rgb + (rgb - blurred) * (amount / 100.0) * 0.55)


def _apply_hsl(rgb: np.ndarray, adjustments: CorrectionAdjustments) -> np.ndarray:
    if not adjustments.hsl:
        return rgb

    hue, sat, value = _rgb_to_hsv(rgb)
    for color, adjustment in adjustments.hsl.items():
        ranges = HUE_RANGES.get(color, ())
        mask = np.zeros_like(hue, dtype=bool)
        for low, high in ranges:
            mask |= (hue >= low) & (hue <= high)
        hue = np.where(mask, hue + adjustment.hue, hue)
        sat = np.where(mask, np.clip(sat * (1 + adjustment.saturation / 100.0), 0.0, 1.0), sat)
        value = np.where(mask, np.clip(value + adjustment.luminance / 100.0 * 0.18, 0.0, 1.0), value)
    return _hsv_to_rgb(hue, sat, value)


def render_preview(image: Image.Image, adjustments: CorrectionAdjustments, max_side: int | None = None) -> Image.Image:
    working = downscale(image.convert("RGB"), max_side or settings.preview_max_side)
    rgb = np.asarray(working).astype(np.float32) / 255.0

    rgb *= 2 ** adjustments.exposure
    rgb = _clip(rgb)
    rgb = _apply_temperature_tint(rgb, adjustments.temperature, adjustments.tint)
    rgb = (rgb - 0.5) * (1 + adjustments.contrast / 100.0) + 0.5
    rgb = _apply_highlights_shadows(rgb, adjustments)
    rgb = _apply_saturation(rgb, adjustments.vibrance, adjustments.saturation)
    rgb = _apply_hsl(rgb, adjustments)

    local_amount = adjustments.clarity * 0.65 + adjustments.texture * 0.25 + adjustments.dehaze * 0.45
    rgb = _apply_local_contrast(rgb, local_amount)

    return Image.fromarray((_clip(rgb) * 255).astype(np.uint8), mode="RGB")

