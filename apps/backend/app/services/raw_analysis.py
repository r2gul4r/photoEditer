from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def analyze_raw(path: Path) -> dict[str, Any]:
    try:
        import rawpy  # type: ignore
    except ImportError:
        return {
            "ok": False,
            "error": "rawpy is not installed. Install tonepilot-backend[raw] to enable RAW analysis.",
        }

    try:
        with rawpy.imread(str(path)) as raw:
            visible = raw.raw_image_visible.astype(np.float32)
            black_levels = [float(level) for level in raw.black_level_per_channel]
            white_level = float(raw.white_level or np.max(visible))
            normalized = np.clip((visible - min(black_levels)) / max(white_level - min(black_levels), 1.0), 0.0, 1.0)
            hist, _ = np.histogram(normalized, bins=256, range=(0.0, 1.0))
            return {
                "ok": True,
                "width": int(visible.shape[1]),
                "height": int(visible.shape[0]),
                "black_level_per_channel": black_levels,
                "white_level": white_level,
                "mean": float(np.mean(normalized)),
                "p99": float(np.percentile(normalized, 99)),
                "histogram_256": hist.astype(int).tolist(),
            }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"RAW analysis failed: {exc}",
        }


def render_raw_to_rgb(path: Path) -> Image.Image:
    try:
        import rawpy  # type: ignore
    except ImportError as exc:
        raise RuntimeError("rawpy is not installed. Install tonepilot-backend[raw] to enable RAW import.") from exc

    try:
        with rawpy.imread(str(path)) as raw:
            rgb = raw.postprocess(
                use_camera_wb=True,
                output_bps=8,
                no_auto_bright=False,
            )
        return Image.fromarray(rgb).convert("RGB")
    except Exception as exc:
        raise RuntimeError(f"RAW render failed: {exc}") from exc
