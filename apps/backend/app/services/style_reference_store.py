from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import numpy as np
from PIL import Image

from app.config import settings
from app.models.schemas import ColorGradeAdjustment, ColorGradingAdjustment, HslAdjustment, StyleReferenceSignal
from app.utils.histograms import as_float_rgb, luma_from_rgb, saturation_from_rgb
from app.utils.image_io import downscale, infer_file_type


MAX_STYLE_REFERENCE_FILES = 12
STYLE_REFERENCE_TYPES = {"jpeg", "png"}


class StyleReferenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class StyleReferenceUpload:
    filename: str
    content: bytes


def _safe_filename(filename: str, fallback: str) -> str:
    stem = Path(filename or fallback).stem or Path(fallback).stem
    safe = "".join(ch for ch in stem if ch.isalnum() or ch in {"-", "_"}).strip("_-")
    return f"{safe or Path(fallback).stem}.jpg"


def _mean_channel_delta(rgb: np.ndarray, mask: np.ndarray, left: int, right: int) -> float:
    if not np.any(mask):
        return 0.0
    return float(np.mean(rgb[..., left][mask]) - np.mean(rgb[..., right][mask]))


def _build_hsl_prior(warmth_bias: float, saturation_mean: float, shadow_blue_bias: float) -> dict[str, HslAdjustment]:
    hsl: dict[str, HslAdjustment] = {}
    saturation_push = max(-12.0, min(14.0, (saturation_mean - 0.28) * 70))
    if warmth_bias > 0.035:
        hsl["orange"] = HslAdjustment(saturation=round(max(3.0, warmth_bias * 90), 2), luminance=2)
        hsl["blue"] = HslAdjustment(saturation=round(min(0.0, -saturation_push * 0.35), 2))
    elif warmth_bias < -0.035:
        hsl["blue"] = HslAdjustment(saturation=round(max(3.0, abs(warmth_bias) * 90), 2), luminance=1)
        hsl["orange"] = HslAdjustment(saturation=round(min(0.0, saturation_push * -0.25), 2), luminance=1)

    if shadow_blue_bias > 0.035:
        current = hsl.get("blue", HslAdjustment())
        hsl["blue"] = HslAdjustment(
            hue=current.hue,
            saturation=round(max(current.saturation, shadow_blue_bias * 110), 2),
            luminance=current.luminance,
        )
    return hsl


def _build_color_grading(shadow_blue_bias: float, highlight_warmth_bias: float) -> ColorGradingAdjustment:
    shadows = ColorGradeAdjustment()
    highlights = ColorGradeAdjustment()
    if shadow_blue_bias > 0.035:
        shadows = ColorGradeAdjustment(hue=212, saturation=round(min(18.0, 4 + shadow_blue_bias * 130), 2), luminance=-1)
    elif shadow_blue_bias < -0.035:
        shadows = ColorGradeAdjustment(hue=36, saturation=round(min(14.0, 3 + abs(shadow_blue_bias) * 110), 2), luminance=0.5)

    if highlight_warmth_bias > 0.035:
        highlights = ColorGradeAdjustment(hue=38, saturation=round(min(16.0, 4 + highlight_warmth_bias * 120), 2), luminance=1)
    elif highlight_warmth_bias < -0.035:
        highlights = ColorGradeAdjustment(hue=205, saturation=round(min(14.0, 3 + abs(highlight_warmth_bias) * 110), 2), luminance=0)

    return ColorGradingAdjustment(shadows=shadows, highlights=highlights, balance=-8, blending=58)


def _summary(
    luma_p50: float,
    luma_std: float,
    saturation_mean: float,
    warmth_bias: float,
    shadow_blue_bias: float,
    highlight_warmth_bias: float,
) -> str:
    parts: list[str] = []
    if luma_p50 > 0.62:
        parts.append("bright")
    elif luma_p50 < 0.38:
        parts.append("low-key")
    if luma_std > 0.22:
        parts.append("contrasty")
    elif luma_std < 0.13:
        parts.append("soft contrast")
    if saturation_mean > 0.36:
        parts.append("saturated")
    elif saturation_mean < 0.18:
        parts.append("muted")
    if warmth_bias > 0.05:
        parts.append("warm")
    elif warmth_bias < -0.05:
        parts.append("cool")
    if shadow_blue_bias > 0.04:
        parts.append("blue shadows")
    if highlight_warmth_bias > 0.04:
        parts.append("warm highlights")
    return ", ".join(parts[:5]) if parts else "balanced reference"


class StyleReferenceStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.records: dict[str, StyleReferenceSignal] = {}

    def save_uploads(self, uploads: list[StyleReferenceUpload]) -> StyleReferenceSignal:
        if not uploads:
            raise StyleReferenceError("At least one style reference image is required")
        if len(uploads) > MAX_STYLE_REFERENCE_FILES:
            raise StyleReferenceError(f"Style reference upload is limited to {MAX_STYLE_REFERENCE_FILES} images")

        reference_id = str(uuid4())
        reference_dir = self.root / reference_id
        reference_dir.mkdir(parents=True, exist_ok=True)
        filenames: list[str] = []
        luma_values: list[float] = []
        luma_std_values: list[float] = []
        saturation_means: list[float] = []
        saturation_p50s: list[float] = []
        warmth_biases: list[float] = []
        tint_biases: list[float] = []
        shadow_blue_biases: list[float] = []
        highlight_warmth_biases: list[float] = []

        for index, upload in enumerate(uploads, start=1):
            file_type = infer_file_type(upload.filename)
            if file_type not in STYLE_REFERENCE_TYPES:
                raise StyleReferenceError("Style references support JPEG and PNG images only")
            if not upload.content:
                raise StyleReferenceError(f"Style reference {upload.filename} is empty")

            try:
                image = Image.open(io.BytesIO(upload.content)).convert("RGB")
            except Exception as exc:
                raise StyleReferenceError(f"Cannot read style reference {upload.filename}: {exc}") from exc

            filename = _safe_filename(upload.filename, f"reference-{index}.jpg")
            downscale(image, 1400).save(reference_dir / filename, format="JPEG", quality=90)
            filenames.append(filename)

            rgb = as_float_rgb(np.asarray(downscale(image, 720)))
            luma = luma_from_rgb(rgb)
            saturation = saturation_from_rgb(rgb)
            shadow_mask = luma < 0.36
            highlight_mask = luma > 0.64
            luma_values.append(float(np.percentile(luma.reshape(-1), 50)))
            luma_std_values.append(float(np.std(luma)))
            saturation_means.append(float(np.mean(saturation)))
            saturation_p50s.append(float(np.percentile(saturation.reshape(-1), 50)))
            warmth_biases.append(float(np.mean(rgb[..., 0]) - np.mean(rgb[..., 2])))
            tint_biases.append(float(np.mean(rgb[..., 1]) - ((np.mean(rgb[..., 0]) + np.mean(rgb[..., 2])) / 2)))
            shadow_blue_biases.append(_mean_channel_delta(rgb, shadow_mask, 2, 0))
            highlight_warmth_biases.append(_mean_channel_delta(rgb, highlight_mask, 0, 2))

        luma_p50 = float(np.mean(luma_values))
        luma_std = float(np.mean(luma_std_values))
        saturation_mean = float(np.mean(saturation_means))
        saturation_p50 = float(np.mean(saturation_p50s))
        warmth_bias = float(np.mean(warmth_biases))
        tint_bias = float(np.mean(tint_biases))
        shadow_blue_bias = float(np.mean(shadow_blue_biases))
        highlight_warmth_bias = float(np.mean(highlight_warmth_biases))

        signal = StyleReferenceSignal(
            style_reference_id=reference_id,
            count=len(filenames),
            filenames=filenames,
            summary=_summary(luma_p50, luma_std, saturation_mean, warmth_bias, shadow_blue_bias, highlight_warmth_bias),
            luma_p50=round(luma_p50, 4),
            luma_std=round(luma_std, 4),
            saturation_mean=round(saturation_mean, 4),
            saturation_p50=round(saturation_p50, 4),
            warmth_bias=round(warmth_bias, 4),
            tint_bias=round(tint_bias, 4),
            shadow_blue_bias=round(shadow_blue_bias, 4),
            highlight_warmth_bias=round(highlight_warmth_bias, 4),
            hsl_prior=_build_hsl_prior(warmth_bias, saturation_mean, shadow_blue_bias),
            color_grading=_build_color_grading(shadow_blue_bias, highlight_warmth_bias),
        )
        self.records[reference_id] = signal
        return signal

    def get(self, reference_id: str) -> StyleReferenceSignal:
        try:
            return self.records[reference_id]
        except KeyError as exc:
            raise KeyError(f"Unknown style_reference_id: {reference_id}") from exc


style_reference_store = StyleReferenceStore(settings.storage_dir / "style-references")
