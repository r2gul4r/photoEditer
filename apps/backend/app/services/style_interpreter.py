from dataclasses import dataclass

from app.models.schemas import StyleInterpretation
from app.services.lut_style_index import match_lut_style_prior
from app.services.preset_style_index import match_preset_style_prior


SliderPrior = dict[str, tuple[float, float]]


@dataclass(frozen=True)
class StyleDefinition:
    style_id: str
    triggers: tuple[str, ...]
    mood: tuple[str, ...]
    targets: tuple[str, ...]
    avoid: tuple[str, ...]
    slider_prior: SliderPrior


COMMON_PRIOR: SliderPrior = {
    "exposure": (-0.05, 0.15),
    "contrast": (-6, 8),
    "highlights": (-18, -2),
    "shadows": (2, 16),
    "whites": (-4, 6),
    "blacks": (-2, 8),
    "temperature": (-120, 120),
    "tint": (-2, 2),
    "vibrance": (2, 12),
    "saturation": (-2, 4),
    "clarity": (-2, 4),
    "texture": (-2, 4),
    "dehaze": (-2, 4),
}


STYLE_DEFINITIONS: tuple[StyleDefinition, ...] = (
    StyleDefinition(
        style_id="soft_film",
        triggers=("청량한 필름톤", "필름", "film", "analog", "빈티지", "레트로"),
        mood=("fresh", "soft", "analog", "clear"),
        targets=("soft contrast", "clean color", "gentle grain-ready tone", "lifted shadows"),
        avoid=("muddy shadows", "heavy orange cast", "crushed blacks"),
        slider_prior={
            **COMMON_PRIOR,
            "exposure": (0.05, 0.35),
            "contrast": (-18, 2),
            "highlights": (-26, -4),
            "shadows": (8, 28),
            "blacks": (4, 16),
            "temperature": (-250, 150),
            "vibrance": (8, 22),
            "saturation": (-6, 4),
            "clarity": (-12, -2),
            "texture": (-10, -2),
            "dehaze": (-10, 0),
        },
    ),
    StyleDefinition(
        style_id="cool_japanese_summer",
        triggers=("시원한 일본 여름", "일본 여름", "시원", "여름", "청량", "파란 하늘", "유카타", "cool summer", "japanese summer"),
        mood=("cool", "bright", "fresh", "summer"),
        targets=("bright high-key image", "clear cyan-blue sky", "fresh green", "soft contrast", "gentle highlights"),
        avoid=("overexposed sky", "blue skin tone", "oversaturated green", "heavy HDR"),
        slider_prior={
            **COMMON_PRIOR,
            "exposure": (0.05, 0.55),
            "contrast": (-20, 5),
            "highlights": (-40, -5),
            "shadows": (5, 35),
            "whites": (-5, 10),
            "blacks": (0, 12),
            "temperature": (-900, -100),
            "tint": (-4, 8),
            "vibrance": (8, 28),
            "saturation": (-4, 10),
            "clarity": (-10, 2),
            "texture": (-8, 2),
            "dehaze": (-8, 2),
        },
    ),
    StyleDefinition(
        style_id="anime_background",
        triggers=("애니메이션", "애니", "만화", "anime", "animation", "일러스트", "배경화면"),
        mood=("clean", "bright", "pastel", "illustration-inspired"),
        targets=("clean color separation", "brighter midtones", "soft highlights", "vivid controlled colors", "slight pastel"),
        avoid=("full anime generation", "neon saturation", "plastic skin tone", "harsh clarity"),
        slider_prior={
            **COMMON_PRIOR,
            "exposure": (0.08, 0.45),
            "contrast": (-12, 8),
            "highlights": (-32, -4),
            "shadows": (8, 26),
            "temperature": (-350, 80),
            "tint": (0, 8),
            "vibrance": (14, 34),
            "saturation": (0, 10),
            "clarity": (-14, -2),
            "texture": (-12, -2),
            "dehaze": (-6, 2),
        },
    ),
    StyleDefinition(
        style_id="warm_cafe",
        triggers=("따뜻한 카페톤", "카페", "따뜻", "감성카페", "warm cafe", "cozy"),
        mood=("warm", "cozy", "soft", "intimate"),
        targets=("warm highlights", "comfortable shadows", "soft contrast", "brown-orange ambience"),
        avoid=("yellow skin", "murky shadows", "overly red whites"),
        slider_prior={
            **COMMON_PRIOR,
            "exposure": (-0.02, 0.25),
            "contrast": (-8, 14),
            "highlights": (-24, -2),
            "shadows": (4, 22),
            "temperature": (250, 950),
            "tint": (2, 10),
            "vibrance": (4, 18),
            "saturation": (-4, 8),
            "clarity": (-8, 4),
            "texture": (-6, 4),
            "dehaze": (-4, 4),
        },
    ),
    StyleDefinition(
        style_id="cinematic_mood",
        triggers=("시네마틱", "영화", "cinematic", "moody", "dramatic"),
        mood=("cinematic", "moody", "dramatic", "controlled"),
        targets=("protected highlights", "deeper blacks", "richer contrast", "cool shadows"),
        avoid=("clipped blacks", "crushed faces", "muddy low contrast"),
        slider_prior={
            **COMMON_PRIOR,
            "exposure": (-0.18, 0.12),
            "contrast": (10, 34),
            "highlights": (-36, -8),
            "shadows": (-8, 10),
            "whites": (-8, 6),
            "blacks": (-22, -4),
            "temperature": (-350, 150),
            "tint": (-4, 6),
            "vibrance": (2, 16),
            "saturation": (-8, 4),
            "clarity": (4, 18),
            "texture": (0, 10),
            "dehaze": (4, 16),
        },
    ),
    StyleDefinition(
        style_id="clean_instagram",
        triggers=("깨끗한 인스타그램톤", "깨끗", "인스타", "clean", "instagram", "화사"),
        mood=("clean", "bright", "balanced", "social"),
        targets=("clear whites", "fresh color", "moderate brightness", "low technical risk"),
        avoid=("overexposed skin", "excessive sharpening", "dirty whites"),
        slider_prior={
            **COMMON_PRIOR,
            "exposure": (0.05, 0.35),
            "contrast": (-6, 10),
            "highlights": (-22, -2),
            "shadows": (4, 20),
            "temperature": (-120, 180),
            "tint": (0, 6),
            "vibrance": (8, 22),
            "saturation": (-2, 6),
            "clarity": (-4, 6),
            "texture": (-6, 2),
            "dehaze": (-4, 2),
        },
    ),
)


def _score_prompt(prompt: str, style: StyleDefinition) -> int:
    normalized = prompt.casefold()
    score = 0
    for trigger in style.triggers:
        trigger_norm = trigger.casefold()
        if trigger_norm in normalized:
            score += 3 + min(len(trigger_norm), 12)
    return score


def _merge_unique(base: tuple[str, ...], extra: list[str]) -> list[str]:
    items: list[str] = []
    for value in [*base, *extra]:
        if value and value not in items:
            items.append(value)
    return items


def _merge_unique_list(base: list[str], extra: list[str]) -> list[str]:
    items: list[str] = []
    for value in [*base, *extra]:
        if value and value not in items:
            items.append(value)
    return items


def _blend_slider_prior(base: SliderPrior, lut_prior: dict[str, list[float]], *, weight: float = 0.55) -> SliderPrior:
    blended: SliderPrior = dict(base)
    for name, lut_bounds in lut_prior.items():
        if not isinstance(lut_bounds, list) or len(lut_bounds) != 2:
            continue
        lut_low, lut_high = float(lut_bounds[0]), float(lut_bounds[1])
        base_low, base_high = blended.get(name, (0.0, 0.0))
        low = base_low * (1 - weight) + lut_low * weight
        high = base_high * (1 - weight) + lut_high * weight
        blended[name] = (round(low, 3), round(high, 3))
    return blended


def interpret_style(style_prompt: str) -> StyleInterpretation:
    prompt = style_prompt.strip()
    best = max(STYLE_DEFINITIONS, key=lambda style: _score_prompt(prompt, style))
    best_score = _score_prompt(prompt, best)
    if best_score == 0:
        best = next(style for style in STYLE_DEFINITIONS if style.style_id == "clean_instagram")
    lut_match = match_lut_style_prior(prompt, style_id=best.style_id if best_score > 0 else None)
    preset_match = match_preset_style_prior(prompt, style_id=best.style_id if best_score > 0 else None)
    slider_prior = best.slider_prior
    mood = list(best.mood)
    targets = list(best.targets)
    avoid = list(best.avoid)
    lut_hsl_prior = {}
    lut_style_group = None
    lut_profile_count = 0
    lut_match_score = 0.0
    preset_hsl_prior = {}
    preset_style_group = None
    preset_profile_count = 0
    preset_match_score = 0.0

    if preset_match:
        slider_prior = _blend_slider_prior(slider_prior, preset_match.get("sliderPrior", {}), weight=0.65)
        mood = _merge_unique_list(mood, preset_match.get("mood", []))
        targets = _merge_unique_list(targets, preset_match.get("targets", []))
        avoid = _merge_unique_list(avoid, preset_match.get("riskNotes", preset_match.get("avoid", [])))
        preset_hsl_prior = preset_match.get("hslPrior", {})
        preset_style_group = preset_match.get("id")
        preset_profile_count = int(preset_match.get("profileCount", 0))
        preset_match_score = float(preset_match.get("matchScore", 0))

    if lut_match:
        slider_prior = _blend_slider_prior(slider_prior, lut_match.get("sliderPrior", {}), weight=0.35 if preset_match else 0.55)
        mood = _merge_unique_list(mood, lut_match.get("mood", []))
        targets = _merge_unique_list(targets, lut_match.get("targets", []))
        avoid = _merge_unique_list(avoid, lut_match.get("avoid", []))
        lut_hsl_prior = lut_match.get("hslPrior", {})
        lut_style_group = lut_match.get("id")
        lut_profile_count = int(lut_match.get("profileCount", 0))
        lut_match_score = float(lut_match.get("matchScore", 0))

    return StyleInterpretation(
        style_id=best.style_id,
        mood=mood,
        targets=targets,
        avoid=avoid,
        slider_prior=slider_prior,
        lut_style_group=lut_style_group,
        lut_profile_count=lut_profile_count,
        lut_match_score=lut_match_score,
        lut_hsl_prior=lut_hsl_prior,
        preset_style_group=preset_style_group,
        preset_profile_count=preset_profile_count,
        preset_match_score=preset_match_score,
        preset_hsl_prior=preset_hsl_prior,
    )
