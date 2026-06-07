from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from app.models.schemas import (
    ColorGradeAdjustment,
    ColorGradingAdjustment,
    CorrectionAdjustments,
    CorrectionCandidate,
    HslAdjustment,
    ImageAnalysis,
    StyleInterpretation,
    StyleReferenceSignal,
)
from app.services.image_analysis import analyze_image
from app.services.raw_analysis import render_raw_to_rgb
from app.services.reference_style_target import ReferenceStyleTarget, build_reference_style_target
from app.services.renderer import render_preview
from app.services.scene_interpreter import SceneInterpretation, interpret_scene
from app.utils.image_io import RAW_EXTENSIONS, load_rgb_image


ADJUSTMENT_LIMITS: dict[str, tuple[float, float]] = {
    "exposure": (-2.0, 2.0),
    "contrast": (-100, 100),
    "highlights": (-100, 100),
    "shadows": (-100, 100),
    "whites": (-100, 100),
    "blacks": (-100, 100),
    "temperature": (-2000, 2000),
    "tint": (-50, 50),
    "vibrance": (-100, 100),
    "saturation": (-100, 100),
    "clarity": (-100, 100),
    "texture": (-100, 100),
    "dehaze": (-100, 100),
}

HSL_BY_STYLE = {
    "cool_japanese_summer": {
        "yellow": {"hue": -3, "saturation": -3, "luminance": 5},
        "green": {"hue": -6, "saturation": 4, "luminance": 10},
        "aqua": {"hue": -7, "saturation": 8, "luminance": 10},
        "blue": {"hue": -5, "saturation": 4, "luminance": 13},
        "orange": {"hue": 0, "saturation": -3, "luminance": 5},
    },
    "anime_background": {
        "green": {"hue": -3, "saturation": 10, "luminance": 8},
        "blue": {"hue": -4, "saturation": 12, "luminance": 10},
        "aqua": {"hue": -5, "saturation": 10, "luminance": 10},
    },
    "soft_film": {
        "green": {"hue": -2, "saturation": -4, "luminance": 8},
        "blue": {"hue": -2, "saturation": -6, "luminance": 8},
        "orange": {"hue": 0, "saturation": -4, "luminance": 4},
    },
    "warm_cafe": {
        "orange": {"hue": -2, "saturation": 6, "luminance": 3},
        "yellow": {"hue": -4, "saturation": -4, "luminance": 2},
        "blue": {"hue": 0, "saturation": -10, "luminance": -2},
    },
    "cinematic_mood": {
        "blue": {"hue": -4, "saturation": 6, "luminance": -6},
        "orange": {"hue": 2, "saturation": 4, "luminance": 3},
        "green": {"hue": -8, "saturation": -8, "luminance": -4},
    },
    "clean_instagram": {
        "orange": {"hue": 0, "saturation": -2, "luminance": 4},
        "green": {"hue": -2, "saturation": 4, "luminance": 5},
        "blue": {"hue": -2, "saturation": 4, "luminance": 5},
    },
}


def _empty_color_grading() -> ColorGradingAdjustment:
    return ColorGradingAdjustment()


def _style_targets_text(style: StyleInterpretation) -> str:
    return " ".join([style.style_id, style.lut_style_group or "", *style.mood, *style.targets]).casefold()


def _grade(hue: float, saturation: float, luminance: float = 0) -> ColorGradeAdjustment:
    return ColorGradeAdjustment(hue=hue, saturation=saturation, luminance=luminance)


def _build_color_grading(style: StyleInterpretation, variant: str, strength: float) -> ColorGradingAdjustment:
    text = _style_targets_text(style)
    variant_scale = {"natural": 0.45, "style": 0.85, "bold": 1.12}[variant] * (0.65 + 0.35 * strength)

    if style.lut_style_group == "teal_orange" or ("cool shadows" in text and "warm highlights" in text):
        return ColorGradingAdjustment(
            shadows=_grade(205, round(12 * variant_scale, 2), round(-2 * variant_scale, 2)),
            midtones=_grade(192, round(3 * variant_scale, 2), 0),
            highlights=_grade(36, round(9 * variant_scale, 2), round(1.5 * variant_scale, 2)),
            balance=-12,
            blending=62,
        )

    if style.style_id == "cinematic_mood" or "blue shadows" in text:
        return ColorGradingAdjustment(
            shadows=_grade(212, round(9 * variant_scale, 2), round(-1.5 * variant_scale, 2)),
            midtones=_grade(200, round(2 * variant_scale, 2), 0),
            highlights=_grade(42, round(4 * variant_scale, 2), round(0.8 * variant_scale, 2)),
            balance=-18,
            blending=56,
        )

    return _empty_color_grading()


@dataclass(frozen=True)
class CandidateBankOption:
    variant: str
    source: str
    adjustments: CorrectionAdjustments


def _clamp(name: str, value: float) -> float:
    low, high = ADJUSTMENT_LIMITS[name]
    return max(low, min(high, value))


def _midpoint(bounds: tuple[float, float]) -> float:
    return (bounds[0] + bounds[1]) / 2


def _target_for_variant(bounds: tuple[float, float], variant: str) -> float:
    low, high = bounds
    mid = _midpoint(bounds)
    if variant == "natural":
        return mid * 0.45
    if variant == "style":
        return mid * 0.85
    direction = 1 if abs(high) >= abs(low) else -1
    return mid + direction * abs(high - low) * 0.18


def _build_adjustments(
    style: StyleInterpretation,
    target: ReferenceStyleTarget,
    variant: str,
    strength: float,
) -> CorrectionAdjustments:
    values: dict[str, float] = {}
    for name in ADJUSTMENT_LIMITS:
        bounds = target.slider_bounds.get(name, style.slider_prior.get(name, (0.0, 0.0)))
        value = _target_for_variant(bounds, variant) * (0.55 + 0.45 * strength)
        values[name] = _clamp(name, round(value, 2))

    hsl_multiplier = {"natural": 0.45, "style": 0.85, "bold": 1.15}[variant] * (0.6 + 0.4 * strength)
    hsl = {}
    for color, adjustment in HSL_BY_STYLE.get(style.style_id, {}).items():
        hsl[color] = {key: round(value * hsl_multiplier, 2) for key, value in adjustment.items()}
    for color, adjustment in target.hsl_targets.items():
        current = hsl.get(color, {})
        hsl[color] = {
            key: round(current.get(key, 0) * 0.45 + getattr(adjustment, key, 0) * hsl_multiplier * 0.55, 2)
            for key in ("hue", "saturation", "luminance")
        }

    if style.style_id == "cool_japanese_summer":
        summer_hsl_floors = {
            "yellow": {"saturation": -4, "luminance": 4},
            "green": {"saturation": 3, "luminance": 7},
            "aqua": {"saturation": 5, "luminance": 8},
            "blue": {"saturation": 2, "luminance": 10},
            "orange": {"saturation": -4, "luminance": 3},
        }
        for color, floors in summer_hsl_floors.items():
            current = hsl.setdefault(color, {"hue": 0, "saturation": 0, "luminance": 0})
            for key, floor in floors.items():
                current[key] = round(max(current.get(key, 0), floor * hsl_multiplier), 2)

    adjustments = CorrectionAdjustments(**values, hsl=hsl, color_grading=_build_color_grading(style, variant, strength))
    if style.style_id == "cool_japanese_summer":
        temperature_floor = {"natural": -120, "style": -240, "bold": -360}[variant]
        adjustments.temperature = max(adjustments.temperature, temperature_floor)
        adjustments.contrast = min(adjustments.contrast, 2 if variant != "bold" else 4)
        adjustments.saturation = min(adjustments.saturation, 3)
        adjustments.clarity = min(adjustments.clarity, 1 if variant != "bold" else 2)
        adjustments.texture = min(adjustments.texture, 1 if variant != "bold" else 2)
        adjustments.dehaze = min(adjustments.dehaze, 0)
    return adjustments


def _apply_histogram_constraints(
    adjustments: CorrectionAdjustments,
    analysis: ImageAnalysis,
    style: StyleInterpretation,
    target: ReferenceStyleTarget,
    variant: str,
) -> list[str]:
    flags = analysis.risk_flags
    warnings: list[str] = []
    hard_constraints = set(target.constraints.hard)

    if flags.highlight_clipping:
        adjustments.exposure = min(adjustments.exposure, 0.12 if variant == "natural" else 0.2)
        adjustments.highlights = min(adjustments.highlights, -28)
        adjustments.whites = min(adjustments.whites, -8)
        warnings.append("하이라이트 클리핑 위험이 있어 노출과 화이트를 제한했어.")

    if flags.too_dark:
        adjustments.exposure = max(adjustments.exposure, 0.22 if variant == "natural" else 0.34)
        adjustments.shadows = max(adjustments.shadows, 18 if variant == "natural" else 28)
        adjustments.blacks = max(adjustments.blacks, 2)
        warnings.append("이미지가 어두워서 암부를 올리고 블랙 크러시를 피했어.")

    if flags.shadow_crushing:
        adjustments.shadows = max(adjustments.shadows, 24)
        adjustments.blacks = max(adjustments.blacks, 8)
        warnings.append("암부 뭉개짐 위험이 있어 shadows/blacks를 보호했어.")

    if flags.too_flat:
        adjustments.contrast = max(adjustments.contrast, 6 if variant != "natural" else 2)

    if flags.too_bright:
        adjustments.exposure = min(adjustments.exposure, 0.05)
        adjustments.highlights = min(adjustments.highlights, -18)
        warnings.append("중간톤이 밝아 추가 노출 상승을 제한했어.")

    if flags.over_saturated:
        adjustments.saturation = min(adjustments.saturation, -6)
        adjustments.vibrance = min(adjustments.vibrance, 10)
        warnings.append("채도가 높아 saturation보다 vibrance 위주로 제한했어.")

    wants_cool = "cool" in style.mood or style.style_id in {"cool_japanese_summer", "anime_background"}
    wants_warm = "warm" in style.mood or style.style_id == "warm_cafe"

    if flags.strong_warm_cast and wants_cool:
        cool_target = {"natural": -160, "style": -220, "bold": -300}[variant] if style.style_id == "cool_japanese_summer" else -320
        adjustments.temperature = min(adjustments.temperature, cool_target)
        warnings.append("따뜻한 컬러 캐스트를 감지해 쿨톤 이동을 적용했어.")

    if flags.strong_cool_cast and "avoid_global_blue_wash" in hard_constraints:
        cool_floor = {"natural": -80, "style": -120, "bold": -160}[variant]
        adjustments.temperature = max(adjustments.temperature, cool_floor)
        adjustments.saturation = min(adjustments.saturation, 0)
        warnings.append("이미 차가운 원본이라 전체 블루 워시를 피하도록 쿨톤을 제한했어.")

    if flags.strong_cool_cast and wants_warm:
        adjustments.temperature = max(adjustments.temperature, 320)
        warnings.append("차가운 컬러 캐스트를 감지해 웜톤 이동을 적용했어.")

    return warnings


def _format_signed(value: float, *, unit: str = "") -> str:
    if value == 0:
        return f"0{unit}"
    prefix = "+" if value > 0 else ""
    return f"{prefix}{value:g}{unit}"


def _dominant_hsl_summary(adjustments: CorrectionAdjustments) -> str:
    hsl = adjustments.hsl or {}
    if not hsl:
        return "HSL은 크게 건드리지 않음"
    strongest: list[tuple[str, str, float]] = []
    for color, values in hsl.items():
        for channel in ("hue", "saturation", "luminance"):
            value = getattr(values, channel, 0)
            if abs(value) >= 1:
                strongest.append((color, channel, value))
    if not strongest:
        return "HSL은 미세 조정만 적용"
    strongest.sort(key=lambda item: abs(item[2]), reverse=True)
    color, channel, value = strongest[0]
    return f"{color} {channel} {_format_signed(value)} 중심"


def _dominant_color_grading_summary(adjustments: CorrectionAdjustments) -> str | None:
    grading = adjustments.color_grading
    entries = [
        ("암부", grading.shadows),
        ("중간톤", grading.midtones),
        ("하이라이트", grading.highlights),
    ]
    active = [(label, grade) for label, grade in entries if grade.saturation >= 1 or abs(grade.luminance) >= 0.5]
    if not active:
        return None
    label, grade = max(active, key=lambda item: item[1].saturation)
    return f"{label} hue {round(grade.hue)} sat {_format_signed(round(grade.saturation, 1))}"


def _analysis_warmth_bias(analysis: ImageAnalysis) -> float:
    return analysis.rgb.r_mean - analysis.rgb.b_mean


def _analysis_tint_bias(analysis: ImageAnalysis) -> float:
    return analysis.rgb.g_mean - ((analysis.rgb.r_mean + analysis.rgb.b_mean) / 2)


def _clamp_delta(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _blend_grade(base: ColorGradeAdjustment, target: ColorGradeAdjustment, weight: float) -> ColorGradeAdjustment:
    if target.saturation <= 0 and abs(target.luminance) < 0.001:
        return base
    return ColorGradeAdjustment(
        hue=round(base.hue * (1 - weight) + target.hue * weight, 2),
        saturation=round(base.saturation * (1 - weight) + target.saturation * weight, 2),
        luminance=round(base.luminance * (1 - weight) + target.luminance * weight, 2),
    )


def _blend_color_grading(
    base: ColorGradingAdjustment,
    target: ColorGradingAdjustment,
    weight: float,
) -> ColorGradingAdjustment:
    return ColorGradingAdjustment(
        shadows=_blend_grade(base.shadows, target.shadows, weight),
        midtones=_blend_grade(base.midtones, target.midtones, weight * 0.75),
        highlights=_blend_grade(base.highlights, target.highlights, weight),
        balance=round(base.balance * (1 - weight) + target.balance * weight, 2),
        blending=round(base.blending * (1 - weight) + target.blending * weight, 2),
    )


def _style_reference_distance(analysis: ImageAnalysis, style_reference: StyleReferenceSignal) -> float:
    return (
        abs(style_reference.luma_p50 - analysis.luma.p50) * 1.25
        + abs(style_reference.luma_std - analysis.luma.std) * 0.9
        + abs(style_reference.saturation_mean - analysis.saturation.mean) * 0.9
        + abs(style_reference.warmth_bias - _analysis_warmth_bias(analysis)) * 1.2
        + abs(style_reference.tint_bias - _analysis_tint_bias(analysis)) * 0.8
    )


def _apply_style_reference_adjustments(
    adjustments: CorrectionAdjustments,
    analysis: ImageAnalysis,
    style_reference: StyleReferenceSignal,
    variant: str,
) -> CorrectionAdjustments:
    copy = adjustments.model_copy(deep=True)
    weight = {"natural": 0.28, "style": 0.5, "bold": 0.68}[variant]

    luma_delta = style_reference.luma_p50 - analysis.luma.p50
    contrast_delta = style_reference.luma_std - analysis.luma.std
    saturation_delta = style_reference.saturation_mean - analysis.saturation.mean
    warmth_delta = style_reference.warmth_bias - _analysis_warmth_bias(analysis)
    tint_delta = style_reference.tint_bias - _analysis_tint_bias(analysis)

    copy.exposure = _clamp("exposure", round(copy.exposure + _clamp_delta(luma_delta * 1.15, -0.28, 0.28) * weight, 2))
    copy.contrast = _clamp("contrast", round(copy.contrast + _clamp_delta(contrast_delta * 90, -18, 18) * weight, 2))
    copy.vibrance = _clamp("vibrance", round(copy.vibrance + _clamp_delta(saturation_delta * 95, -22, 22) * weight, 2))
    copy.saturation = _clamp("saturation", round(copy.saturation + _clamp_delta(saturation_delta * 55, -14, 14) * weight, 2))
    copy.temperature = _clamp("temperature", round(copy.temperature + _clamp_delta(warmth_delta * 2200, -520, 520) * weight, 2))
    copy.tint = _clamp("tint", round(copy.tint + _clamp_delta(tint_delta * 160, -14, 14) * weight, 2))

    for color, target in style_reference.hsl_prior.items():
        current = copy.hsl.get(color, HslAdjustment())
        copy.hsl[color] = HslAdjustment(
            hue=_clamp_hsl_value(current.hue * (1 - weight) + target.hue * weight),
            saturation=_clamp_hsl_value(current.saturation * (1 - weight) + target.saturation * weight),
            luminance=_clamp_hsl_value(current.luminance * (1 - weight) + target.luminance * weight),
        )
    copy.color_grading = _blend_color_grading(copy.color_grading, style_reference.color_grading, weight)
    return copy


def build_candidate_explanations(
    adjustments: CorrectionAdjustments,
    warnings: list[str],
    *,
    intent: str,
    reference_note: str | None = None,
) -> dict[str, str]:
    tone_parts = [
        f"노출 {_format_signed(adjustments.exposure, unit='EV')}",
        f"대비 {_format_signed(adjustments.contrast)}",
        f"하이라이트 {_format_signed(adjustments.highlights)}",
        f"섀도우 {_format_signed(adjustments.shadows)}",
    ]
    color_parts = [
        f"색온도 {_format_signed(adjustments.temperature, unit='K')}",
        f"틴트 {_format_signed(adjustments.tint)}",
        f"생동감 {_format_signed(adjustments.vibrance)}",
        f"채도 {_format_signed(adjustments.saturation)}",
        _dominant_hsl_summary(adjustments),
    ]
    grading_summary = _dominant_color_grading_summary(adjustments)
    if grading_summary:
        color_parts.append(grading_summary)
    risk_items = [*warnings]
    if reference_note:
        risk_items.append(reference_note)
    risk_summary = " / ".join(risk_items) if risk_items else "클리핑/과채도 보호 제한 없음"
    return {
        "intent": intent,
        "tone_summary": ", ".join(tone_parts),
        "color_summary": ", ".join(color_parts),
        "risk_summary": risk_summary,
    }


def _clamp_hsl_value(value: float) -> float:
    return round(max(-100.0, min(100.0, value)), 2)


def _offset_adjustments(
    adjustments: CorrectionAdjustments,
    offsets: dict[str, float],
    *,
    hsl_scale: float = 1.0,
    hsl_offsets: dict[str, dict[str, float]] | None = None,
) -> CorrectionAdjustments:
    copy = adjustments.model_copy(deep=True)
    for name, offset in offsets.items():
        if name in ADJUSTMENT_LIMITS:
            setattr(copy, name, _clamp(name, round(float(getattr(copy, name, 0)) + offset, 2)))

    if copy.hsl and hsl_scale != 1.0:
        copy.hsl = {
            color: HslAdjustment(
                hue=_clamp_hsl_value(adjustment.hue * hsl_scale),
                saturation=_clamp_hsl_value(adjustment.saturation * hsl_scale),
                luminance=_clamp_hsl_value(adjustment.luminance * hsl_scale),
            )
            for color, adjustment in copy.hsl.items()
        }

    for color, channels in (hsl_offsets or {}).items():
        current = copy.hsl.get(color, HslAdjustment())
        copy.hsl[color] = HslAdjustment(
            hue=_clamp_hsl_value(current.hue + channels.get("hue", 0)),
            saturation=_clamp_hsl_value(current.saturation + channels.get("saturation", 0)),
            luminance=_clamp_hsl_value(current.luminance + channels.get("luminance", 0)),
        )
    return copy


def _candidate_seeds(
    base: CorrectionAdjustments,
    target: ReferenceStyleTarget,
    variant: str,
) -> list[CandidateBankOption]:
    constraints = set(target.constraints.hard)
    seeds = [CandidateBankOption(variant=variant, source="reference_midpoint", adjustments=base)]
    seeds.append(
        CandidateBankOption(
            variant=variant,
            source="highlight_safe",
            adjustments=_offset_adjustments(
                base,
                {"exposure": -0.04, "highlights": -7, "whites": -4, "contrast": -2},
                hsl_scale=0.96,
            ),
        )
    )
    if "protect_shadows" in constraints or "lift_dark_midtones_safely" in constraints:
        seeds.append(
            CandidateBankOption(
                variant=variant,
                source="shadow_safe",
                adjustments=_offset_adjustments(base, {"exposure": 0.05, "shadows": 8, "blacks": 4}, hsl_scale=0.98),
            )
        )
    if "limit_saturation" in constraints:
        seeds.append(
            CandidateBankOption(
                variant=variant,
                source="saturation_safe",
                adjustments=_offset_adjustments(base, {"vibrance": -5, "saturation": -7}, hsl_scale=0.82),
            )
        )
    if "avoid_global_blue_wash" in constraints:
        blue_wash_guard = {"natural": 35, "style": 60, "bold": 90}[variant]
        seeds.append(
            CandidateBankOption(
                variant=variant,
                source="blue_wash_guard",
                adjustments=_offset_adjustments(
                    base,
                    {
                        "temperature": blue_wash_guard,
                        "vibrance": -4,
                        "saturation": -3,
                        "clarity": -2,
                        "texture": -1,
                        "dehaze": -2,
                    },
                    hsl_scale=0.82,
                ),
            )
        )
        seeds.append(
            CandidateBankOption(
                variant=variant,
                source="summer_region_style",
                adjustments=_offset_adjustments(
                    base,
                    {"temperature": blue_wash_guard * 0.55, "highlights": -5, "shadows": 3},
                    hsl_scale=0.94,
                    hsl_offsets={
                        "blue": {"luminance": 2},
                        "aqua": {"luminance": 1.5},
                        "green": {"saturation": -1, "luminance": 1.5},
                        "orange": {"saturation": 1, "luminance": 1.5},
                    },
                ),
            )
        )
    else:
        seeds.append(
            CandidateBankOption(
                variant=variant,
                source="style_color_push",
                adjustments=_offset_adjustments(base, {"vibrance": 3, "saturation": 1}, hsl_scale=1.06),
            )
        )

    return seeds


def _add_scene_seed_options(
    seeds: list[CandidateBankOption],
    base: CorrectionAdjustments,
    variant: str,
    scene: SceneInterpretation | None,
) -> None:
    if scene is None:
        return
    if scene.has_region("sky", min_coverage=0.04):
        seeds.append(
            CandidateBankOption(
                variant=variant,
                source="scene_sky_protect",
                adjustments=_offset_adjustments(
                    base,
                    {"highlights": -7, "whites": -3, "temperature": 25},
                    hsl_scale=0.96,
                    hsl_offsets={"blue": {"saturation": -1, "luminance": 3}, "aqua": {"luminance": 2}},
                ),
            )
        )
    if scene.has_region("foliage", min_coverage=0.04):
        seeds.append(
            CandidateBankOption(
                variant=variant,
                source="scene_foliage_fresh",
                adjustments=_offset_adjustments(
                    base,
                    {"vibrance": -2, "saturation": -1, "clarity": -1},
                    hsl_scale=0.96,
                    hsl_offsets={"green": {"hue": -2, "saturation": -2, "luminance": 3}, "yellow": {"saturation": -2}},
                ),
            )
        )
    if scene.has_region("skin", min_coverage=0.01):
        seeds.append(
            CandidateBankOption(
                variant=variant,
                source="scene_skin_protect",
                adjustments=_offset_adjustments(
                    base,
                    {"temperature": 45, "tint": 1, "vibrance": -3, "saturation": -2, "clarity": -2},
                    hsl_scale=0.9,
                    hsl_offsets={"orange": {"saturation": 2, "luminance": 2}, "red": {"saturation": -1}},
                ),
            )
        )
    if scene.has_region("white_neutral", min_coverage=0.03):
        seeds.append(
            CandidateBankOption(
                variant=variant,
                source="scene_neutral_anchor",
                adjustments=_offset_adjustments(base, {"temperature": 40 if base.temperature < 0 else -20, "tint": -base.tint * 0.35}),
            )
        )
    if scene.has_region("shadow", min_coverage=0.08):
        seeds.append(
            CandidateBankOption(
                variant=variant,
                source="scene_shadow_rolloff",
                adjustments=_offset_adjustments(base, {"shadows": 6, "blacks": 4, "contrast": -2, "dehaze": -2}, hsl_scale=0.97),
            )
        )


def build_candidate_bank(
    style: StyleInterpretation,
    target: ReferenceStyleTarget,
    strength: float,
    scene: SceneInterpretation | None = None,
) -> dict[str, list[CandidateBankOption]]:
    bank: dict[str, list[CandidateBankOption]] = {}
    for variant in ("natural", "style", "bold"):
        base = _build_adjustments(style, target, variant, strength)
        seeds = _candidate_seeds(base, target, variant)
        _add_scene_seed_options(seeds, base, variant, scene)
        bank[variant] = seeds
    return bank


def _load_source_image(source_path: Path | None, file_type: str | None) -> Image.Image | None:
    if source_path is None:
        return None
    path = Path(source_path)
    if not path.exists():
        return None
    try:
        if file_type == "raw" or path.suffix.lower() in RAW_EXTENSIONS:
            return render_raw_to_rgb(path)
        return load_rgb_image(path)
    except Exception:
        return None


def _adjustment_shape_score(
    adjustments: CorrectionAdjustments,
    analysis: ImageAnalysis,
    target: ReferenceStyleTarget,
    variant: str,
    scene: SceneInterpretation | None,
) -> float:
    base_score = {"natural": 0.88, "style": 0.82, "bold": 0.75}[variant]
    score = base_score + (target.confidence - 0.5) * 0.05
    constraints = set(target.constraints.hard)

    magnitude = (
        abs(adjustments.exposure) * 0.04
        + abs(adjustments.temperature) / 2000 * 0.04
        + (abs(adjustments.contrast) + abs(adjustments.clarity) + abs(adjustments.dehaze)) / 300 * 0.05
        + (abs(adjustments.vibrance) + abs(adjustments.saturation)) / 200 * 0.04
        + (
            adjustments.color_grading.shadows.saturation
            + adjustments.color_grading.midtones.saturation
            + adjustments.color_grading.highlights.saturation
        )
        / 300
        * 0.03
    )
    score -= min(0.12, magnitude)

    if "protect_highlights" in constraints:
        if adjustments.exposure > 0.14:
            score -= 0.05
        if adjustments.highlights > -12:
            score -= 0.05
        if adjustments.whites > 4:
            score -= 0.04
    if "limit_saturation" in constraints and (adjustments.saturation > 0 or adjustments.vibrance > 14):
        score -= 0.08
    if "avoid_global_blue_wash" in constraints:
        blue = adjustments.hsl.get("blue", HslAdjustment())
        orange = adjustments.hsl.get("orange", HslAdjustment())
        if adjustments.temperature < -260:
            score -= 0.08
        if adjustments.color_grading.shadows.saturation > 6:
            score -= 0.06
        if adjustments.saturation > 3:
            score -= 0.06
        if blue.saturation > 8 and orange.saturation < -6:
            score -= 0.08
        if analysis.risk_flags.strong_cool_cast and adjustments.temperature < -120:
            score -= 0.1
    if scene is not None:
        if scene.has_region("skin", min_coverage=0.01):
            orange = adjustments.hsl.get("orange", HslAdjustment())
            if adjustments.temperature < -220:
                score -= 0.08
            if orange.saturation < -8:
                score -= 0.06
            if adjustments.clarity > 4:
                score -= 0.04
        if scene.has_region("white_neutral", min_coverage=0.03) and abs(adjustments.temperature) > 420:
            score -= 0.05
        if scene.has_region("sky", min_coverage=0.04):
            blue = adjustments.hsl.get("blue", HslAdjustment())
            if blue.luminance > 0 and adjustments.highlights <= -8:
                score += 0.025
            if blue.saturation > 12:
                score -= 0.04
        if scene.has_region("foliage", min_coverage=0.04):
            green = adjustments.hsl.get("green", HslAdjustment())
            if green.luminance > 0 and green.saturation <= 8:
                score += 0.025
            if green.saturation > 14:
                score -= 0.06
    return score


def _rendered_analysis_score(
    before: ImageAnalysis,
    after: ImageAnalysis,
    target: ReferenceStyleTarget,
    scene: SceneInterpretation | None,
    style_reference: StyleReferenceSignal | None,
) -> float:
    score = 0.0
    constraints = set(target.constraints.hard)

    if after.risk_flags.highlight_clipping:
        score -= 0.14
    if after.risk_flags.shadow_crushing:
        score -= 0.12
    if after.risk_flags.over_saturated:
        score -= 0.1
    if after.risk_flags.too_bright and "protect_highlights" in constraints:
        score -= 0.08
    if after.risk_flags.too_dark and "lift_dark_midtones_safely" in constraints:
        score -= 0.07

    if "avoid_global_blue_wash" in constraints:
        before_blue_bias = before.rgb.b_mean - before.rgb.r_mean
        after_blue_bias = after.rgb.b_mean - after.rgb.r_mean
        if after.risk_flags.strong_cool_cast:
            score -= 0.16
        if after_blue_bias - before_blue_bias > 0.07:
            score -= 0.12
        if after_blue_bias > 0.1:
            score -= 0.08
        if 0.4 <= after.luma.p50 <= 0.74 and after.saturation.p95 < 0.88:
            score += 0.05

    if before.risk_flags.highlight_clipping and not after.risk_flags.highlight_clipping:
        score += 0.08
    if before.risk_flags.shadow_crushing and not after.risk_flags.shadow_crushing:
        score += 0.06
    if before.risk_flags.over_saturated and not after.risk_flags.over_saturated:
        score += 0.06
    if scene is not None and scene.has_region("white_neutral", min_coverage=0.03):
        color_bias = max(
            abs(after.rgb.r_mean - after.rgb.g_mean),
            abs(after.rgb.b_mean - after.rgb.g_mean),
        )
        if color_bias > 0.12:
            score -= 0.05
    if style_reference is not None:
        before_distance = _style_reference_distance(before, style_reference)
        after_distance = _style_reference_distance(after, style_reference)
        score += _clamp_delta((before_distance - after_distance) * 0.4, -0.12, 0.14)
    return score


def _select_best_adjustments(
    seeds: list[CandidateBankOption],
    analysis: ImageAnalysis,
    target: ReferenceStyleTarget,
    variant: str,
    source_image: Image.Image | None,
    scene: SceneInterpretation | None,
    style_reference: StyleReferenceSignal | None,
) -> tuple[CorrectionAdjustments, float, list[str]]:
    best_adjustments = seeds[0].adjustments
    best_score = -1.0
    scoring_warnings: list[str] = []
    for option in seeds:
        seed = option.adjustments
        score = _adjustment_shape_score(seed, analysis, target, variant, scene)
        if option.source.startswith("scene_"):
            score += 0.02
        if style_reference is not None and option.source.endswith("_user_reference"):
            score += 0.06
        if source_image is not None:
            try:
                rendered = render_preview(source_image, seed, max_side=320)
                score += _rendered_analysis_score(analysis, analyze_image(rendered), target, scene, style_reference)
            except Exception as exc:
                message = f"{option.source} 프리뷰 점수 계산을 건너뛰었어: {exc.__class__.__name__}"
                if message not in scoring_warnings:
                    scoring_warnings.append(message)
        if score > best_score:
            best_adjustments = seed
            best_score = score
    return best_adjustments, round(max(0.1, min(0.98, best_score)), 2), scoring_warnings


def _reference_note(
    target: ReferenceStyleTarget,
    used_source_preview: bool,
    scene: SceneInterpretation | None,
    style_reference: StyleReferenceSignal | None,
) -> str | None:
    if style_reference is not None:
        return f"사용자 레퍼런스 {style_reference.count}장({style_reference.summary}) 쪽으로 밝기/채도/색분리를 맞췄어."
    if not target.reference_groups and not target.constraints.hard:
        return None
    groups = ", ".join(f"{signal.source}:{signal.group_id}" for signal in target.reference_groups)
    scene_note = f" scene:{','.join(scene.scene_tags)}" if scene and scene.scene_tags else ""
    if used_source_preview and groups:
        return f"레퍼런스({groups})와 장면 해석{scene_note} 기반 프리뷰 점수로 후보를 선택했어."
    if groups:
        return f"레퍼런스({groups}) 타깃 범위와 장면 해석{scene_note}으로 후보를 제한했어."
    return "원본 위험 플래그 기반 제약으로 후보를 제한했어."


def generate_recommendations(
    analysis: ImageAnalysis,
    style: StyleInterpretation,
    strength: float = 0.7,
    source_path: Path | None = None,
    file_type: str | None = None,
    style_reference: StyleReferenceSignal | None = None,
) -> list[CorrectionCandidate]:
    candidates: list[CorrectionCandidate] = []
    target = build_reference_style_target(analysis, style)
    source_image = _load_source_image(source_path, file_type)
    scene = interpret_scene(source_image) if source_image is not None else None
    candidate_bank = build_candidate_bank(style, target, strength, scene)
    labels = {
        "natural": ("Natural", "레퍼런스 타깃 안에서 원본을 크게 해치지 않는 안전한 기본 보정"),
        "style": ("Style", "레퍼런스 분위기와 원본 안전성을 함께 맞춘 균형형 보정"),
        "bold": ("Bold", "레퍼런스 방향을 더 강하게 적용한 후보. 위험 플래그가 있으면 주의"),
    }

    for index, variant in enumerate(("natural", "style", "bold")):
        options: list[CandidateBankOption] = []
        warnings: list[str] = []
        for option in candidate_bank[variant]:
            adjusted = option.adjustments.model_copy(deep=True)
            option_warnings = _apply_histogram_constraints(adjusted, analysis, style, target, variant)
            if not warnings:
                warnings = option_warnings
            options.append(CandidateBankOption(variant=option.variant, source=option.source, adjustments=adjusted))
            if style_reference is not None:
                reference_adjusted = _apply_style_reference_adjustments(adjusted, analysis, style_reference, variant)
                _apply_histogram_constraints(reference_adjusted, analysis, style, target, variant)
                options.append(
                    CandidateBankOption(
                        variant=option.variant,
                        source=f"{option.source}_user_reference",
                        adjustments=reference_adjusted,
                    )
                )
        if variant == "bold" and (analysis.risk_flags.highlight_clipping or analysis.risk_flags.over_saturated):
            warnings.append("Bold 후보는 클리핑/과채도 위험이 커질 수 있어 preview 확인이 필요해.")

        adjustments, score, scoring_warnings = _select_best_adjustments(
            options,
            analysis,
            target,
            variant,
            source_image,
            scene,
            style_reference,
        )
        for warning in scoring_warnings:
            if warning not in warnings:
                warnings.append(warning)
        score = round(max(0.1, score - len(warnings) * 0.015 - index * 0.005), 2)
        name, description = labels[variant]
        explanations = build_candidate_explanations(
            adjustments,
            warnings,
            intent=description,
            reference_note=_reference_note(target, source_image is not None, scene, style_reference),
        )
        candidates.append(
            CorrectionCandidate(
                id=variant,  # type: ignore[arg-type]
                name=name,
                description=description,
                adjustments=adjustments,
                score=score,
                warnings=warnings,
                **explanations,
            )
        )

    return candidates

