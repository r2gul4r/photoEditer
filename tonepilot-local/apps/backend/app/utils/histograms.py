import numpy as np


def as_float_rgb(rgb: np.ndarray) -> np.ndarray:
    arr = np.asarray(rgb)
    if arr.dtype.kind in {"u", "i"}:
        max_value = np.iinfo(arr.dtype).max
        arr = arr.astype(np.float32) / float(max_value)
    else:
        arr = arr.astype(np.float32)
    return np.clip(arr, 0.0, 1.0)


def histogram_256(values: np.ndarray) -> list[int]:
    counts, _ = np.histogram(np.clip(values, 0.0, 1.0), bins=256, range=(0.0, 1.0))
    return counts.astype(int).tolist()


def percentile_stats(values: np.ndarray) -> dict[str, float | list[int]]:
    flat = np.asarray(values, dtype=np.float32).reshape(-1)
    p01, p05, p50, p95, p99 = np.percentile(flat, [1, 5, 50, 95, 99])
    return {
        "mean": float(np.mean(flat)),
        "std": float(np.std(flat)),
        "p01": float(p01),
        "p05": float(p05),
        "p50": float(p50),
        "p95": float(p95),
        "p99": float(p99),
        "histogram_256": histogram_256(flat),
    }


def luma_from_rgb(rgb: np.ndarray) -> np.ndarray:
    arr = as_float_rgb(rgb)
    return (0.2126 * arr[..., 0]) + (0.7152 * arr[..., 1]) + (0.0722 * arr[..., 2])


def saturation_from_rgb(rgb: np.ndarray) -> np.ndarray:
    arr = as_float_rgb(rgb)
    max_channel = np.max(arr, axis=-1)
    min_channel = np.min(arr, axis=-1)
    chroma = max_channel - min_channel
    return np.where(max_channel <= 1e-6, 0.0, chroma / max_channel)

