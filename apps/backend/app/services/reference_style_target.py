from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import HslAdjustment, ImageAnalysis, StyleInterpretation


SliderBounds = dict[str, tuple[float, float]]


@dataclass(frozen=True)
class ReferenceGroupSignal:
    source: str
    group_id: str
    profile_count: int
    match_score: float


@dataclass(frozen=True)
class StyleConstraintSet:
    hard: tuple[str, ...]
    soft: tuple[str, ...]


@dataclass(frozen=True)
class ReferenceStyleTarget:
    style_id: str
    reference_groups: tuple[ReferenceGroupSignal, ...]
    mood_axes: dict[str, float]
    slider_bounds: SliderBounds
    hsl_targets: dict[str, HslAdjustment]
    constraints: StyleConstraintSet
    confidence: float
    trace: tuple[str, ...]


def _add_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _group_signals(style: StyleInterpretation) -> tuple[ReferenceGroupSignal, ...]:
    signals: list[ReferenceGroupSignal] = []
    if style.preset_style_group:
        signals.append(
            ReferenceGroupSignal(
                source="preset",
                group_id=style.preset_style_group,
                profile_count=style.preset_profile_count,
                match_score=style.preset_match_score,
            )
        )
    if style.lut_style_group:
        signals.append(
            ReferenceGroupSignal(
                source="lut",
                group_id=style.lut_style_group,
                profile_count=style.lut_profile_count,
                match_score=style.lut_match_score,
            )
        )
    return tuple(signals)


def _tighten_high(bounds: SliderBounds, name: str, high: float) -> None:
    if name not in bounds:
        return
    low, current_high = bounds[name]
    current_high = min(current_high, high)
    if low > current_high:
        low = current_high
    bounds[name] = (round(low, 3), round(current_high, 3))


def _tighten_low(bounds: SliderBounds, name: str, low: float) -> None:
    if name not in bounds:
        return
    current_low, high = bounds[name]
    current_low = max(current_low, low)
    if current_low > high:
        high = current_low
    bounds[name] = (round(current_low, 3), round(high, 3))


def _merge_hsl_targets(style: StyleInterpretation) -> dict[str, HslAdjustment]:
    targets: dict[str, HslAdjustment] = {}

    def merge(source: dict[str, HslAdjustment], weight: float) -> None:
        for color, adjustment in source.items():
            current = targets.get(color, HslAdjustment())
            targets[color] = HslAdjustment(
                hue=round(current.hue * (1 - weight) + adjustment.hue * weight, 2),
                saturation=round(current.saturation * (1 - weight) + adjustment.saturation * weight, 2),
                luminance=round(current.luminance * (1 - weight) + adjustment.luminance * weight, 2),
            )

    merge(style.preset_hsl_prior, 0.65)
    merge(style.lut_hsl_prior, 0.55 if targets else 0.7)
    return targets


def _mood_axes(style: StyleInterpretation, analysis: ImageAnalysis) -> dict[str, float]:
    mood = {value.casefold() for value in style.mood}
    targets = " ".join(style.targets).casefold()
    axes = {
        "cool": 1.0 if "cool" in mood else 0.0,
        "warm": 1.0 if "warm" in mood else 0.0,
        "bright": 1.0 if "bright" in mood or "high-key" in targets else 0.0,
        "soft": 1.0 if "soft" in mood or "soft" in targets else 0.0,
        "contrast": 1.0 if "contrast" in targets else 0.0,
        "saturation": 1.0 if "vivid" in targets or "vibrant" in mood else 0.0,
    }
    if analysis.risk_flags.highlight_clipping or analysis.risk_flags.too_bright:
        axes["highlight_safety"] = 1.0
    if analysis.risk_flags.shadow_crushing or analysis.risk_flags.too_dark:
        axes["shadow_safety"] = 1.0
    if style.style_id == "cool_japanese_summer":
        axes.update(
            {
                "daylight": 1.0,
                "cool_night": -1.0,
                "global_blue_wash": -1.0,
                "sky_luminance": 0.9,
                "foliage_freshness": 0.75,
                "skin_protection": 1.0,
            }
        )
    return axes


def _confidence(signals: tuple[ReferenceGroupSignal, ...]) -> float:
    if not signals:
        return 0.35
    profile_count = sum(signal.profile_count for signal in signals)
    match_score = sum(signal.match_score for signal in signals)
    return round(min(1.0, 0.45 + min(profile_count / 120, 0.35) + min(match_score / 120, 0.2)), 2)


def build_reference_style_target(analysis: ImageAnalysis, style: StyleInterpretation) -> ReferenceStyleTarget:
    bounds = {name: (float(low), float(high)) for name, (low, high) in style.slider_prior.items()}
    hard: list[str] = []
    soft: list[str] = []
    for item in style.avoid:
        _add_unique(soft, item)

    flags = analysis.risk_flags
    if flags.highlight_clipping:
        _add_unique(hard, "protect_highlights")
        _tighten_high(bounds, "exposure", 0.18)
        _tighten_high(bounds, "highlights", -18)
        _tighten_high(bounds, "whites", -6)
    if flags.too_bright:
        _add_unique(hard, "avoid_extra_exposure")
        _tighten_high(bounds, "exposure", 0.08)
        _tighten_high(bounds, "highlights", -16)
    if flags.shadow_crushing:
        _add_unique(hard, "protect_shadows")
        _tighten_low(bounds, "shadows", 16)
        _tighten_low(bounds, "blacks", 4)
    if flags.too_dark:
        _add_unique(hard, "lift_dark_midtones_safely")
        _tighten_low(bounds, "exposure", 0.12)
        _tighten_low(bounds, "shadows", 18)
    if flags.over_saturated:
        _add_unique(hard, "limit_saturation")
        _tighten_high(bounds, "saturation", 0)
        _tighten_high(bounds, "vibrance", 12)

    if style.style_id == "cool_japanese_summer":
        for constraint in (
            "avoid_global_blue_wash",
            "avoid_cool_night",
            "protect_skin_hue",
            "protect_highlights",
            "avoid_neon_foliage",
        ):
            _add_unique(hard, constraint)
        _tighten_low(bounds, "temperature", -340)
        _tighten_high(bounds, "temperature", -40)
        _tighten_high(bounds, "contrast", 2)
        _tighten_high(bounds, "saturation", 3)
        _tighten_high(bounds, "vibrance", 22)
        _tighten_high(bounds, "clarity", 1)
        _tighten_high(bounds, "texture", 1)
        _tighten_high(bounds, "dehaze", 0)
        if flags.strong_warm_cast:
            _tighten_low(bounds, "temperature", -260)
            _tighten_high(bounds, "temperature", -120)
        if flags.strong_cool_cast:
            _tighten_low(bounds, "temperature", -160)

    signals = _group_signals(style)
    trace: list[str] = []
    for signal in signals:
        trace.append(f"{signal.source}:{signal.group_id}:{signal.profile_count}")
    if hard:
        trace.append("constraints:" + ",".join(hard))

    return ReferenceStyleTarget(
        style_id=style.style_id,
        reference_groups=signals,
        mood_axes=_mood_axes(style, analysis),
        slider_bounds=bounds,
        hsl_targets=_merge_hsl_targets(style),
        constraints=StyleConstraintSet(hard=tuple(hard), soft=tuple(soft)),
        confidence=_confidence(signals),
        trace=tuple(trace),
    )
