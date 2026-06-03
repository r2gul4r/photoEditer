from pathlib import Path
from typing import Any
import importlib.util

import numpy as np
from PIL import Image

from app.models.schemas import RawSupportStatus


RAW_INSTALL_HINT = 'Install optional backend dependencies with: pip install -e "apps/backend[raw]"'


def raw_support_status() -> RawSupportStatus:
    if importlib.util.find_spec("rawpy") is None:
        return RawSupportStatus(
            available=False,
            message="RAW import is disabled because rawpy is not installed.",
            install_hint=RAW_INSTALL_HINT,
        )
    try:
        import rawpy  # type: ignore
    except Exception as exc:
        return RawSupportStatus(
            available=False,
            message=f"RAW import is disabled because rawpy could not be imported: {exc}",
            install_hint=RAW_INSTALL_HINT,
        )
    return RawSupportStatus(
        available=True,
        version=str(getattr(rawpy, "__version__", "unknown")),
        message="RAW import is available.",
        install_hint=RAW_INSTALL_HINT,
    )


def analyze_raw(path: Path) -> dict[str, Any]:
    try:
        import rawpy  # type: ignore
    except ImportError:
        return {
            "ok": False,
            "code": "rawpy_missing",
            "error": "rawpy is not installed. RAW analysis is disabled.",
            "install_hint": RAW_INSTALL_HINT,
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
            "code": "raw_analysis_failed",
            "error": f"RAW analysis failed: {exc}",
            "install_hint": RAW_INSTALL_HINT,
        }


def render_raw_to_rgb(path: Path) -> Image.Image:
    try:
        import rawpy  # type: ignore
    except ImportError as exc:
        raise RuntimeError(f"rawpy is not installed. RAW import is disabled. {RAW_INSTALL_HINT}") from exc

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
