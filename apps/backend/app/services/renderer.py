import colorsys

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

CROP_ASPECTS = {
    "square": 1.0,
    "landscape": 16 / 9,
    "portrait": 4 / 5,
}


def _clip(rgb: np.ndarray) -> np.ndarray:
    return np.clip(rgb, 0.0, 1.0)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _smoothstep(edge0: float, edge1: float, value: np.ndarray) -> np.ndarray:
    t = np.clip((value - edge0) / max(edge1 - edge0, 1e-6), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _apply_geometry(image: Image.Image, adjustments: CorrectionAdjustments) -> Image.Image:
    rotation = adjustments.rotation_degrees % 360
    if rotation:
        # CSS positive rotation is clockwise; Pillow positive rotation is counter-clockwise.
        image = image.rotate(-rotation, expand=True)

    aspect = CROP_ASPECTS.get(adjustments.crop_aspect)
    if aspect is None:
        return image

    width, height = image.size
    if width <= 0 or height <= 0:
        return image

    current_aspect = width / height
    if current_aspect > aspect:
        crop_width = int(height * aspect)
        left = max(0, (width - crop_width) // 2)
        image = image.crop((left, 0, left + crop_width, height))
    else:
        crop_height = int(width / aspect)
        top = max(0, (height - crop_height) // 2)
        image = image.crop((0, top, width, top + crop_height))
    return image


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


def _apply_color_grade(rgb: np.ndarray, hue: float, saturation: float, luminance: float, weight: np.ndarray) -> np.ndarray:
    sat_amount = _clamp01(saturation / 100.0)
    luma_amount = max(-1.0, min(1.0, luminance / 100.0))
    if sat_amount <= 0 and abs(luma_amount) < 0.001:
        return rgb

    grade_color = np.asarray(colorsys.hsv_to_rgb((hue % 360.0) / 360.0, 1.0, 1.0), dtype=np.float32)
    chroma_weight = weight[..., None] * sat_amount * 0.32
    graded = rgb * (1.0 - chroma_weight) + grade_color * chroma_weight
    graded += weight[..., None] * luma_amount * 0.16
    return _clip(graded)


def _apply_color_grading(rgb: np.ndarray, adjustments: CorrectionAdjustments) -> np.ndarray:
    grading = adjustments.color_grading
    if (
        grading.shadows.saturation <= 0
        and grading.midtones.saturation <= 0
        and grading.highlights.saturation <= 0
        and abs(grading.shadows.luminance) < 0.001
        and abs(grading.midtones.luminance) < 0.001
        and abs(grading.highlights.luminance) < 0.001
    ):
        return rgb

    luma = luma_from_rgb(rgb)
    blend = 0.45 + _clamp01(grading.blending / 100.0) * 0.55
    balance = max(-1.0, min(1.0, grading.balance / 100.0))
    shadow_edge = 0.58 + balance * 0.12
    highlight_edge = 0.42 + balance * 0.12
    shadow_weight = (np.clip((shadow_edge - luma) / max(shadow_edge, 1e-6), 0.0, 1.0) ** 1.25) * blend
    highlight_weight = (np.clip((luma - highlight_edge) / max(1.0 - highlight_edge, 1e-6), 0.0, 1.0) ** 1.25) * blend
    midtone_weight = (1.0 - np.clip(np.abs(luma - 0.5) / 0.34, 0.0, 1.0)) ** 1.2 * blend * 0.72

    rgb = _apply_color_grade(
        rgb,
        grading.shadows.hue,
        grading.shadows.saturation,
        grading.shadows.luminance,
        shadow_weight,
    )
    rgb = _apply_color_grade(
        rgb,
        grading.midtones.hue,
        grading.midtones.saturation,
        grading.midtones.luminance,
        midtone_weight,
    )
    return _apply_color_grade(
        rgb,
        grading.highlights.hue,
        grading.highlights.saturation,
        grading.highlights.luminance,
        highlight_weight,
    )


def _apply_local_contrast(rgb: np.ndarray, amount: float) -> np.ndarray:
    if abs(amount) < 0.1:
        return rgb
    image = Image.fromarray((_clip(rgb) * 255).astype(np.uint8))
    blurred = np.asarray(image.filter(ImageFilter.GaussianBlur(radius=3))).astype(np.float32) / 255.0
    return _clip(rgb + (rgb - blurred) * (amount / 100.0) * 0.55)


def _apply_noise_reduction(rgb: np.ndarray, amount: float) -> np.ndarray:
    amount = _clamp01(amount / 100.0)
    if amount <= 0:
        return rgb

    image = Image.fromarray((_clip(rgb) * 255).astype(np.uint8))
    radius = 0.35 + amount * 0.95
    gaussian = np.asarray(image.filter(ImageFilter.GaussianBlur(radius=radius))).astype(np.float32) / 255.0
    median = np.asarray(image.filter(ImageFilter.MedianFilter(size=3))).astype(np.float32) / 255.0
    smoothed = gaussian * 0.72 + median * 0.28

    luma = luma_from_rgb(rgb)
    grad_y, grad_x = np.gradient(luma)
    edge_strength = np.sqrt(grad_x * grad_x + grad_y * grad_y)
    edge_threshold = max(float(np.percentile(edge_strength, 92)), 0.012)
    edge_protection = np.clip(edge_strength / edge_threshold, 0.0, 1.0)
    flat_area = (1.0 - edge_protection) ** 1.4
    shadow_weight = 0.72 + (1.0 - luma) * 0.28
    blend = (0.08 + amount * 0.34) * flat_area * shadow_weight
    return _clip(rgb * (1.0 - blend[..., None]) + smoothed * blend[..., None])


def _apply_vignette_correction(rgb: np.ndarray, amount: float) -> np.ndarray:
    amount = _clamp01(amount / 100.0)
    if amount <= 0:
        return rgb

    height, width = rgb.shape[:2]
    y = np.linspace(-1.0, 1.0, height, dtype=np.float32)
    x = np.linspace(-1.0, 1.0, width, dtype=np.float32)
    xx, yy = np.meshgrid(x, y)
    distance = np.clip(np.sqrt(xx * xx + yy * yy) / np.sqrt(2.0), 0.0, 1.0)
    radial = _smoothstep(0.38, 1.0, distance)
    luma = luma_from_rgb(rgb)
    center_pixels = luma[distance < 0.42]
    edge_pixels = luma[distance > 0.78]
    center_luma = float(np.median(center_pixels)) if center_pixels.size else float(np.median(luma))
    edge_luma = float(np.median(edge_pixels)) if edge_pixels.size else center_luma
    falloff = max(0.0, center_luma - edge_luma)
    adaptive_strength = 0.035 + min(0.12, falloff * 0.65)
    if falloff < 0.025:
        adaptive_strength *= 0.35
    highlight_protection = 1.0 - _smoothstep(0.72, 0.96, luma)
    lift = radial * amount * adaptive_strength * highlight_protection
    return _clip(rgb + (1.0 - rgb) * lift[..., None])


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
    working = _apply_geometry(image.convert("RGB"), adjustments)
    working = downscale(working, max_side or settings.preview_max_side)
    rgb = np.asarray(working).astype(np.float32) / 255.0

    rgb *= 2 ** adjustments.exposure
    rgb = _clip(rgb)
    rgb = _apply_temperature_tint(rgb, adjustments.temperature, adjustments.tint)
    rgb = (rgb - 0.5) * (1 + adjustments.contrast / 100.0) + 0.5
    rgb = _apply_highlights_shadows(rgb, adjustments)
    rgb = _apply_saturation(rgb, adjustments.vibrance, adjustments.saturation)
    rgb = _apply_color_grading(rgb, adjustments)
    rgb = _apply_hsl(rgb, adjustments)
    rgb = _apply_noise_reduction(rgb, adjustments.noise_reduction)
    rgb = _apply_vignette_correction(rgb, adjustments.vignette_correction)

    local_amount = adjustments.clarity * 0.65 + adjustments.texture * 0.25 + adjustments.dehaze * 0.45
    rgb = _apply_local_contrast(rgb, local_amount)

    return Image.fromarray((_clip(rgb) * 255).astype(np.uint8), mode="RGB")

