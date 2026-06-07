import numpy as np
from PIL import Image

from app.models.schemas import ColorGradeAdjustment, ColorGradingAdjustment, CorrectionAdjustments
from app.services.renderer import render_preview


def test_renderer_smoke_changes_pixels_and_downscales() -> None:
    source = Image.fromarray(np.full((80, 120, 3), 120, dtype=np.uint8), mode="RGB")
    adjustments = CorrectionAdjustments(
        exposure=0.35,
        contrast=12,
        highlights=-10,
        shadows=8,
        temperature=-300,
        vibrance=18,
        hsl={"blue": {"hue": -3, "saturation": 8, "luminance": 8}},
    )

    preview = render_preview(source, adjustments, max_side=64)

    assert max(preview.size) == 64
    assert preview.mode == "RGB"
    assert np.asarray(preview).mean() != np.asarray(source.resize(preview.size)).mean()


def test_renderer_applies_geometry() -> None:
    source = Image.fromarray(np.full((80, 120, 3), 120, dtype=np.uint8), mode="RGB")
    preview = render_preview(
        source,
        CorrectionAdjustments(rotation_degrees=90, crop_aspect="square"),
        max_side=512,
    )

    assert preview.size == (80, 80)


def test_denoise_reduces_flat_noise_without_destroying_edges() -> None:
    rng = np.random.default_rng(7)
    base = np.zeros((80, 120, 3), dtype=np.float32)
    base[:, :60, :] = 82
    base[:, 60:, :] = 176
    noisy = np.clip(base + rng.normal(0, 16, size=base.shape), 0, 255).astype(np.uint8)
    source = Image.fromarray(noisy, mode="RGB")
    baseline = render_preview(source, CorrectionAdjustments(), max_side=512)
    preview = render_preview(source, CorrectionAdjustments(noise_reduction=70), max_side=512)

    baseline_pixels = np.asarray(baseline).astype(np.float32)
    pixels = np.asarray(preview).astype(np.float32)

    assert pixels[:, 8:48].std() < baseline_pixels[:, 8:48].std() * 0.92
    assert pixels[:, 72:112].std() < baseline_pixels[:, 72:112].std() * 0.92
    baseline_edge = baseline_pixels[:, 72:88].mean() - baseline_pixels[:, 32:48].mean()
    preview_edge = pixels[:, 72:88].mean() - pixels[:, 32:48].mean()
    assert preview_edge > baseline_edge * 0.9


def test_lens_vignette_correction_lifts_dark_edges_subtly() -> None:
    height, width = 90, 120
    y = np.linspace(-1.0, 1.0, height, dtype=np.float32)
    x = np.linspace(-1.0, 1.0, width, dtype=np.float32)
    xx, yy = np.meshgrid(x, y)
    distance = np.clip(np.sqrt(xx * xx + yy * yy) / np.sqrt(2.0), 0.0, 1.0)
    value = 176 - (distance**1.8) * 62
    source = Image.fromarray(np.repeat(value[..., None], 3, axis=2).astype(np.uint8), mode="RGB")

    baseline = render_preview(source, CorrectionAdjustments(), max_side=512)
    preview = render_preview(source, CorrectionAdjustments(vignette_correction=70), max_side=512)
    baseline_pixels = np.asarray(baseline).astype(np.float32)
    pixels = np.asarray(preview).astype(np.float32)

    assert pixels[:10, :10].mean() > baseline_pixels[:10, :10].mean() + 3
    assert abs(pixels[40:50, 55:65].mean() - baseline_pixels[40:50, 55:65].mean()) < 2


def test_color_grading_pushes_shadows_without_washing_highlights() -> None:
    gradient = np.linspace(42, 220, 120, dtype=np.uint8)
    source_arr = np.repeat(gradient[None, :, None], 80, axis=0)
    source = Image.fromarray(np.repeat(source_arr, 3, axis=2), mode="RGB")

    preview = render_preview(
        source,
        CorrectionAdjustments(
            color_grading=ColorGradingAdjustment(
                shadows=ColorGradeAdjustment(hue=212, saturation=18, luminance=-1),
                highlights=ColorGradeAdjustment(hue=38, saturation=10, luminance=1),
                balance=-10,
                blending=65,
            )
        ),
        max_side=512,
    )
    pixels = np.asarray(preview).astype(np.float32)

    shadow_patch = pixels[:, :32, :]
    highlight_patch = pixels[:, -32:, :]
    assert shadow_patch[..., 2].mean() - shadow_patch[..., 0].mean() > 5
    assert highlight_patch[..., 0].mean() - highlight_patch[..., 2].mean() > 2

