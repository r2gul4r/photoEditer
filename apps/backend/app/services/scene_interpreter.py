from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from app.utils.histograms import as_float_rgb, luma_from_rgb, saturation_from_rgb
from app.utils.image_io import downscale


@dataclass(frozen=True)
class SceneRegionStats:
    name: str
    coverage: float
    luma_mean: float
    saturation_mean: float
    hue_mean: float | None
    role: str


@dataclass(frozen=True)
class SceneInterpretation:
    regions: dict[str, SceneRegionStats]
    scene_tags: tuple[str, ...]
    protection_priorities: tuple[str, ...]
    creative_opportunities: tuple[str, ...]

    def has_region(self, name: str, *, min_coverage: float = 0.02) -> bool:
        region = self.regions.get(name)
        return bool(region and region.coverage >= min_coverage)


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


def _circular_hue_mean(hue: np.ndarray, mask: np.ndarray) -> float | None:
    if not np.any(mask):
        return None
    radians = np.deg2rad(hue[mask])
    angle = np.arctan2(float(np.mean(np.sin(radians))), float(np.mean(np.cos(radians))))
    return round(float(np.rad2deg(angle) % 360), 2)


def _region_stats(
    name: str,
    role: str,
    mask: np.ndarray,
    hue: np.ndarray,
    saturation: np.ndarray,
    luma: np.ndarray,
    total_pixels: int,
) -> SceneRegionStats | None:
    coverage = float(np.mean(mask)) if total_pixels else 0.0
    if coverage < 0.005:
        return None
    return SceneRegionStats(
        name=name,
        coverage=round(coverage, 4),
        luma_mean=round(float(np.mean(luma[mask])), 4),
        saturation_mean=round(float(np.mean(saturation[mask])), 4),
        hue_mean=_circular_hue_mean(hue, mask),
        role=role,
    )


def _add_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def interpret_scene(image: Image.Image, *, max_side: int = 360) -> SceneInterpretation:
    working = downscale(image.convert("RGB"), max_side)
    rgb = as_float_rgb(np.asarray(working))
    height, width = rgb.shape[:2]
    total_pixels = max(1, height * width)
    hue, hsv_sat, value = _rgb_to_hsv(rgb)
    luma = luma_from_rgb(rgb)
    saturation = saturation_from_rgb(rgb)

    y = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None]
    upper = y < 0.55
    sky_mask = upper & (hue >= 185) & (hue <= 245) & (value > 0.45) & (hsv_sat > 0.12)
    foliage_mask = (hue >= 65) & (hue <= 165) & (hsv_sat > 0.16) & (value > 0.16)
    skin_mask = (hue >= 8) & (hue <= 48) & (hsv_sat > 0.12) & (hsv_sat < 0.72) & (value > 0.28) & (value < 0.96)
    white_mask = (saturation < 0.09) & (luma > 0.68)
    shadow_mask = luma < 0.22

    candidates = (
        ("sky", "style carrier", sky_mask),
        ("foliage", "style carrier", foliage_mask),
        ("skin", "protected subject", skin_mask),
        ("white_neutral", "neutral anchor", white_mask),
        ("shadow", "tone anchor", shadow_mask),
    )
    regions: dict[str, SceneRegionStats] = {}
    for name, role, mask in candidates:
        stats = _region_stats(name, role, mask, hue, saturation, luma, total_pixels)
        if stats:
            regions[name] = stats

    tags: list[str] = []
    protections: list[str] = []
    opportunities: list[str] = []

    if regions.get("sky", SceneRegionStats("sky", 0, 0, 0, None, "")).coverage >= 0.08:
        _add_unique(tags, "sky_present")
        _add_unique(opportunities, "shape sky brightness and cyan-blue clarity locally")
        _add_unique(protections, "avoid clipping or over-cyan sky")
    if regions.get("foliage", SceneRegionStats("foliage", 0, 0, 0, None, "")).coverage >= 0.08:
        _add_unique(tags, "foliage_present")
        _add_unique(opportunities, "shape foliage hue and freshness without neon greens")
        _add_unique(protections, "avoid neon or muddy foliage")
    if regions.get("skin", SceneRegionStats("skin", 0, 0, 0, None, "")).coverage >= 0.015:
        _add_unique(tags, "skin_present")
        _add_unique(protections, "protect skin hue and saturation")
    if regions.get("white_neutral", SceneRegionStats("white_neutral", 0, 0, 0, None, "")).coverage >= 0.04:
        _add_unique(tags, "neutral_anchor_present")
        _add_unique(protections, "protect neutral whites from color cast")
    if regions.get("shadow", SceneRegionStats("shadow", 0, 0, 0, None, "")).coverage >= 0.12:
        _add_unique(tags, "deep_shadows_present")
        _add_unique(protections, "avoid crushed shadows")
    if not tags:
        _add_unique(tags, "low_semantic_confidence")
        _add_unique(protections, "prefer conservative global edits")

    return SceneInterpretation(
        regions=regions,
        scene_tags=tuple(tags),
        protection_priorities=tuple(protections),
        creative_opportunities=tuple(opportunities),
    )
