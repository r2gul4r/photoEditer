import numpy as np


def as_float_rgb(rgb: np.ndarray) -> np.ndarray:
    arr = np.asarray(rgb)
    if arr.dtype.kind in {"u", "i"}:
        max_value = np.iinfo(arr.dtype).max
        arr = arr.astype(np.float32) / float(max_value)
    else:
        arr = arr.astype(np.float32)
    return np.clip(arr, 0.0, 1.0)


def quantize_to_uint8(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values)
    if arr.dtype.kind in {"u", "i"}:
        max_value = np.iinfo(arr.dtype).max
        if max_value == 255:
            return np.clip(arr, 0, 255).astype(np.uint8)
        clipped = np.clip(arr.astype(np.float32), 0.0, float(max_value))
        return np.rint((clipped / float(max_value)) * 255.0).astype(np.uint8)

    clipped = np.clip(arr.astype(np.float32), 0.0, 1.0)
    return np.rint(clipped * 255.0).astype(np.uint8)


def histogram_256(values: np.ndarray) -> list[int]:
    quantized = quantize_to_uint8(values).reshape(-1)
    counts = np.bincount(quantized, minlength=256)
    return counts.astype(int).tolist()


def histogram_channel(values: np.ndarray) -> dict[str, float | int | list[int]]:
    quantized = quantize_to_uint8(values).reshape(-1)
    counts = np.bincount(quantized, minlength=256).astype(int)
    total = int(quantized.size)
    black = int(counts[0])
    white = int(counts[255])
    return {
        "bins": counts.tolist(),
        "max_count": int(counts.max()) if total else 0,
        "clip_black": black,
        "clip_white": white,
        "clip_black_ratio": float(black / total) if total else 0.0,
        "clip_white_ratio": float(white / total) if total else 0.0,
    }


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


def display_histogram_from_rgb(rgb: np.ndarray) -> dict[str, object]:
    arr = as_float_rgb(rgb)
    luma = luma_from_rgb(arr)
    r = arr[..., 0]
    g = arr[..., 1]
    b = arr[..., 2]

    channels = {
        "luma": histogram_channel(luma),
        "r": histogram_channel(r),
        "g": histogram_channel(g),
        "b": histogram_channel(b),
    }

    r_u8 = quantize_to_uint8(r)
    g_u8 = quantize_to_uint8(g)
    b_u8 = quantize_to_uint8(b)
    total = int(arr.shape[0] * arr.shape[1]) if arr.ndim >= 2 else int(arr.size // 3)
    shadow_clip = int(np.count_nonzero((r_u8 == 0) | (g_u8 == 0) | (b_u8 == 0)))
    highlight_clip = int(np.count_nonzero((r_u8 == 255) | (g_u8 == 255) | (b_u8 == 255)))

    return {
        "bin_count": 256,
        "range_min": 0,
        "range_max": 255,
        "total_pixels": total,
        "max_count": max(int(channel["max_count"]) for channel in channels.values()),
        "shadow_clip": shadow_clip,
        "highlight_clip": highlight_clip,
        "shadow_clip_ratio": float(shadow_clip / total) if total else 0.0,
        "highlight_clip_ratio": float(highlight_clip / total) if total else 0.0,
        "channels": channels,
    }

