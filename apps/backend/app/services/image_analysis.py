import numpy as np
from PIL import Image

from app.models.schemas import ImageAnalysis, LumaStats, RgbStats, RiskFlags, SaturationStats
from app.utils.histograms import as_float_rgb, histogram_256, luma_from_rgb, percentile_stats, saturation_from_rgb


def analyze_rgb_array(rgb: np.ndarray) -> ImageAnalysis:
    arr = as_float_rgb(rgb)
    luma = luma_from_rgb(arr)
    saturation = saturation_from_rgb(arr)

    luma_stats = percentile_stats(luma)
    saturation_p50, saturation_p95 = np.percentile(saturation.reshape(-1), [50, 95])
    r = arr[..., 0].reshape(-1)
    g = arr[..., 1].reshape(-1)
    b = arr[..., 2].reshape(-1)

    highlight_ratio = float(np.mean(luma > 0.98))
    shadow_ratio = float(np.mean(luma < 0.03))

    r_mean = float(np.mean(r))
    b_mean = float(np.mean(b))

    risk_flags = RiskFlags(
        highlight_clipping=bool(luma_stats["p99"] > 0.985 or highlight_ratio > 0.01),
        shadow_crushing=bool(luma_stats["p01"] < 0.01 and shadow_ratio > 0.05),
        too_dark=bool(luma_stats["p50"] < 0.32),
        too_bright=bool(luma_stats["p50"] > 0.72),
        too_flat=bool(luma_stats["std"] < 0.12),
        over_saturated=bool(float(saturation_p95) > 0.9),
        strong_warm_cast=bool(r_mean - b_mean > 0.08),
        strong_cool_cast=bool(b_mean - r_mean > 0.08),
    )

    return ImageAnalysis(
        luma=LumaStats(**luma_stats),
        rgb=RgbStats(
            r_mean=r_mean,
            g_mean=float(np.mean(g)),
            b_mean=b_mean,
            histogram_256={
                "r": histogram_256(r),
                "g": histogram_256(g),
                "b": histogram_256(b),
            },
        ),
        saturation=SaturationStats(
            mean=float(np.mean(saturation)),
            p50=float(saturation_p50),
            p95=float(saturation_p95),
            histogram_256=histogram_256(saturation),
        ),
        risk_flags=risk_flags,
    )


def analyze_image(image: Image.Image) -> ImageAnalysis:
    return analyze_rgb_array(np.asarray(image.convert("RGB")))

