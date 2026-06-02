from dataclasses import dataclass

from app.models.schemas import StyleInterpretation


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


def interpret_style(style_prompt: str) -> StyleInterpretation:
    prompt = style_prompt.strip()
    best = max(STYLE_DEFINITIONS, key=lambda style: _score_prompt(prompt, style))
    if _score_prompt(prompt, best) == 0:
        best = next(style for style in STYLE_DEFINITIONS if style.style_id == "clean_instagram")

    return StyleInterpretation(
        style_id=best.style_id,
        mood=list(best.mood),
        targets=list(best.targets),
        avoid=list(best.avoid),
        slider_prior=best.slider_prior,
    )

