from app.models.schemas import CorrectionAdjustments, CorrectionCandidate, ImageAnalysis, StyleInterpretation


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
        "green": {"hue": -4, "saturation": 6, "luminance": 10},
        "aqua": {"hue": -4, "saturation": 8, "luminance": 8},
        "blue": {"hue": -3, "saturation": 8, "luminance": 10},
        "orange": {"hue": 0, "saturation": -2, "luminance": 3},
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


def _build_adjustments(style: StyleInterpretation, variant: str, strength: float) -> CorrectionAdjustments:
    values: dict[str, float] = {}
    for name in ADJUSTMENT_LIMITS:
        bounds = style.slider_prior.get(name, (0.0, 0.0))
        value = _target_for_variant(bounds, variant) * (0.55 + 0.45 * strength)
        values[name] = _clamp(name, round(value, 2))

    hsl_multiplier = {"natural": 0.45, "style": 0.85, "bold": 1.15}[variant] * (0.6 + 0.4 * strength)
    hsl = {}
    for color, adjustment in HSL_BY_STYLE.get(style.style_id, {}).items():
        hsl[color] = {key: round(value * hsl_multiplier, 2) for key, value in adjustment.items()}
    for color, adjustment in style.lut_hsl_prior.items():
        current = hsl.get(color, {})
        hsl[color] = {
            key: round(current.get(key, 0) * 0.45 + getattr(adjustment, key, 0) * hsl_multiplier * 0.55, 2)
            for key in ("hue", "saturation", "luminance")
        }

    return CorrectionAdjustments(**values, hsl=hsl)


def _apply_histogram_constraints(adjustments: CorrectionAdjustments, analysis: ImageAnalysis, style: StyleInterpretation, variant: str) -> list[str]:
    flags = analysis.risk_flags
    warnings: list[str] = []

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
        adjustments.temperature = min(adjustments.temperature, -320)
        warnings.append("따뜻한 컬러 캐스트를 감지해 쿨톤 이동을 적용했어.")

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


def build_candidate_explanations(
    adjustments: CorrectionAdjustments,
    warnings: list[str],
    *,
    intent: str,
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
    risk_summary = " / ".join(warnings) if warnings else "클리핑/과채도 보호 제한 없음"
    return {
        "intent": intent,
        "tone_summary": ", ".join(tone_parts),
        "color_summary": ", ".join(color_parts),
        "risk_summary": risk_summary,
    }


def generate_recommendations(analysis: ImageAnalysis, style: StyleInterpretation, strength: float = 0.7) -> list[CorrectionCandidate]:
    candidates: list[CorrectionCandidate] = []
    labels = {
        "natural": ("Natural", "원본을 크게 해치지 않는 안전한 기본 보정"),
        "style": ("Style", "키워드 분위기가 더 분명한 균형형 보정"),
        "bold": ("Bold", "효과가 강한 후보. 위험 플래그가 있으면 더 주의해서 확인"),
    }

    for index, variant in enumerate(("natural", "style", "bold")):
        adjustments = _build_adjustments(style, variant, strength)
        warnings = _apply_histogram_constraints(adjustments, analysis, style, variant)
        if variant == "bold" and (analysis.risk_flags.highlight_clipping or analysis.risk_flags.over_saturated):
            warnings.append("Bold 후보는 클리핑/과채도 위험이 커질 수 있어 preview 확인이 필요해.")

        score = round(max(0.1, 0.88 - index * 0.07 - len(warnings) * 0.025), 2)
        name, description = labels[variant]
        explanations = build_candidate_explanations(adjustments, warnings, intent=description)
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

