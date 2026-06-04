from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.models.schemas import LutStyleProfile
from app.services.lut_analysis import LutAnalysisError, load_lut_style_profiles


SLIDER_LIMITS: dict[str, tuple[float, float]] = {
    "exposure": (-0.7, 0.7),
    "contrast": (-55, 55),
    "highlights": (-55, 55),
    "shadows": (-55, 55),
    "whites": (-40, 40),
    "blacks": (-40, 40),
    "temperature": (-1600, 1600),
    "tint": (-35, 35),
    "vibrance": (-45, 45),
    "saturation": (-40, 40),
    "clarity": (-30, 30),
    "texture": (-25, 25),
    "dehaze": (-30, 30),
}

PRIOR_HALF_WIDTH: dict[str, float] = {
    "exposure": 0.12,
    "contrast": 9,
    "highlights": 10,
    "shadows": 10,
    "whites": 8,
    "blacks": 8,
    "temperature": 260,
    "tint": 7,
    "vibrance": 8,
    "saturation": 7,
    "clarity": 6,
    "texture": 5,
    "dehaze": 6,
}

HSL_COLORS = ("red", "orange", "yellow", "green", "aqua", "blue", "purple", "magenta")


@dataclass(frozen=True)
class StyleGroupDefinition:
    group_id: str
    label: str
    keywords: tuple[str, ...]
    mood: tuple[str, ...]
    targets: tuple[str, ...]
    avoid: tuple[str, ...]


STYLE_GROUPS: tuple[StyleGroupDefinition, ...] = (
    StyleGroupDefinition(
        "wedding_warm",
        "Wedding Warm",
        ("wedding", "bridal", "warmwedding", "coolwedding", "\uc6e8\ub529", "\uacb0\ud63c"),
        ("warm", "soft", "skin-friendly", "event"),
        ("warm skin tone", "soft highlight rolloff", "gentle contrast"),
        ("orange skin", "clipped dress highlights", "muddy indoor shadows"),
    ),
    StyleGroupDefinition(
        "beauty_skin",
        "Beauty Skin",
        ("beauty", "skin", "skintone", "face", "smile", "\ud53c\ubd80", "\uc778\ubb3c", "\uc2a4\ud0a8"),
        ("clean", "polished", "skin-friendly"),
        ("smooth skin color", "clean midtones", "controlled saturation"),
        ("plastic skin", "magenta cast", "over-softened detail"),
    ),
    StyleGroupDefinition(
        "lumix_realtime",
        "Lumix Real Time",
        ("lumix", "s5ii", "s5iix", "rtl", "real time", "v-log", "vlog", "driftwood", "\ub8e8\ubbf9\uc2a4", "\ube0c\uc774\ub85c\uadf8"),
        ("camera-ready", "balanced", "rec709"),
        ("V-Log to display-ready contrast", "camera-friendly color", "moderate saturation"),
        ("double-normalized contrast", "too much log correction", "hard clipping"),
    ),
    StyleGroupDefinition(
        "panasonic_rec709",
        "Panasonic Rec709 Utility",
        ("panasonic", "varicam", "rec709", "709", "v709", "logc", "n-log", "flog", "cineon", "\ud30c\ub098\uc18c\ub2c9"),
        ("technical", "neutral", "display-ready"),
        ("clean Rec709 transform", "safe contrast", "predictable color"),
        ("stacking multiple transforms", "crushed log shadows", "overcorrected highlights"),
    ),
    StyleGroupDefinition(
        "teal_orange",
        "Teal Orange",
        ("teal", "orange", "cyan", "aqua", "blockbuster", "\ud2f8", "\uc624\ub80c\uc9c0"),
        ("cinematic", "split-tone", "stylized"),
        ("cool shadows", "warm highlights", "separated blues and oranges"),
        ("blue skin", "neon cyan", "oversaturated orange"),
    ),
    StyleGroupDefinition(
        "cool_night",
        "Cool Night",
        ("night", "dusk", "cold", "cool", "blue", "icy", "noir", "horror", "\uc57c\uacbd", "\ucc28\uac00\uc6b4"),
        ("cool", "moody", "low-key"),
        ("cool shadows", "protected highlights", "night atmosphere"),
        ("dead skin tone", "crushed blacks", "flat blue cast"),
    ),
    StyleGroupDefinition(
        "warm_sunset",
        "Warm Sunset",
        ("sunset", "golden", "warm", "dawn", "sepia", "kodak", "kodakchrome", "vintage vibes", "\ub178\uc744", "\ub530\ub73b"),
        ("warm", "glowing", "nostalgic"),
        ("warm highlights", "golden midtones", "gentle color warmth"),
        ("yellow whites", "orange skin", "brown color cast"),
    ),
    StyleGroupDefinition(
        "film_vintage",
        "Film Vintage",
        ("film", "vintage", "chrome", "provia", "astia", "eterna", "velvia", "classic", "nostalgic", "reala", "fuji", "\ud544\ub984", "\ube48\ud2f0\uc9c0"),
        ("analog", "nostalgic", "film-like"),
        ("film color separation", "controlled saturation", "soft rolloff"),
        ("dirty whites", "overdone emulation", "muddy greens"),
    ),
    StyleGroupDefinition(
        "monochrome",
        "Monochrome",
        ("mono", "bandw", "b&w", "black and white", "achromic", "acros", "\ud751\ubc31", "\ubaa8\ub178"),
        ("monochrome", "graphic", "contrast"),
        ("black and white tonality", "strong luma separation", "controlled contrast"),
        ("blocked shadows", "featureless highlights", "unwanted color residue"),
    ),
    StyleGroupDefinition(
        "pastel_soft",
        "Pastel Soft",
        ("pastel", "pastelkrome", "dreamy", "faded", "soft", "\ud30c\uc2a4\ud154", "\ubd80\ub4dc\ub7ec\uc6b4"),
        ("soft", "pastel", "light"),
        ("soft contrast", "pastel saturation", "lifted shadows"),
        ("washed-out subject", "weak blacks", "colorless mids"),
    ),
    StyleGroupDefinition(
        "vibrant_pop",
        "Vibrant Pop",
        ("pop", "vibrant", "velvia", "colorful", "rgbman", "redman", "greenman", "blueman", "\uc0c9\uac10", "\ube44\ube44\ub4dc"),
        ("vibrant", "colorful", "punchy"),
        ("strong color presence", "clear hue separation", "lively saturation"),
        ("oversaturation", "neon colors", "skin color drift"),
    ),
    StyleGroupDefinition(
        "clean_natural",
        "Clean Natural",
        ("clean", "natural", "protect", "denoise", "neutral", "standard", "\uc790\uc5f0", "\uae54\ub054"),
        ("clean", "natural", "safe"),
        ("low-risk correction", "natural color", "protected highlight detail"),
        ("boring flat output", "weak style signal", "clinical color"),
    ),
    StyleGroupDefinition(
        "cinematic_mood",
        "Cinematic Mood",
        ("cinema", "cinematic", "movie", "drama", "moody", "se7en", "bladerunner", "apocalypse", "\uc2dc\ub124\ub9c8", "\uc601\ud654"),
        ("cinematic", "dramatic", "controlled"),
        ("stronger contrast", "mood color", "controlled highlight rolloff"),
        ("overly crushed blacks", "heavy color cast", "HDR-looking contrast"),
    ),
)

GROUP_BY_ID = {group.group_id: group for group in STYLE_GROUPS}
DEFAULT_GROUP_ID = "cinematic_mood"
CLASSIFICATION_PRIORITY = (
    "wedding_warm",
    "beauty_skin",
    "monochrome",
    "pastel_soft",
    "vibrant_pop",
    "teal_orange",
    "cool_night",
    "warm_sunset",
    "film_vintage",
    "clean_natural",
)

STYLE_ID_GROUP_HINTS: dict[str, dict[str, int]] = {
    "soft_film": {"film_vintage": 10, "pastel_soft": 6},
    "cool_japanese_summer": {"cool_night": 8, "pastel_soft": 4},
    "anime_background": {"pastel_soft": 8, "vibrant_pop": 4},
    "warm_cafe": {"warm_sunset": 8},
    "cinematic_mood": {"cinematic_mood": 10},
    "clean_instagram": {"clean_natural": 6},
}

EXPLICIT_GROUP_BOOSTS: dict[str, tuple[str, ...]] = {
    "wedding_warm": ("wedding", "bridal", "\uc6e8\ub529", "\uacb0\ud63c"),
    "beauty_skin": ("beauty", "skin", "skintone", "\ud53c\ubd80", "\uc778\ubb3c", "\uc2a4\ud0a8"),
    "lumix_realtime": ("lumix", "real time", "rtl", "s5ii", "\ub8e8\ubbf9\uc2a4"),
    "panasonic_rec709": ("panasonic", "rec709", "v709", "\ud30c\ub098\uc18c\ub2c9"),
    "teal_orange": ("teal orange", "teal", "cyan orange", "\ud2f8 \uc624\ub80c\uc9c0"),
    "monochrome": ("monochrome", "black and white", "b&w", "mono", "\ud751\ubc31", "\ubaa8\ub178"),
}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _reference_root() -> Path:
    return _project_root() / "reference"


def _normalize_text(value: str | None) -> str:
    return re.sub(r"[^a-z0-9\uac00-\ud7a3]+", " ", (value or "").casefold()).strip()


def _source_key(profile: LutStyleProfile) -> str:
    url = profile.metadata.sourceUrl or ""
    parts = url.split("/")
    if len(parts) >= 5:
        return "/".join(parts[2:5])
    return "user_import"


def _family_key(profile: LutStyleProfile) -> str:
    text = _normalize_text(profile.concept or profile.title or profile.id)
    text = re.sub(r"\b(17|33|65|cube|size|vlt|lut|srgb|rec709|vlog|v-log|nle|davinci|resolve)\b", " ", text)
    text = re.sub(r"\b(e|r|to|for|and|the|pack|free)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or profile.metadata.sha256[:12]


def _score_group(text: str, group: StyleGroupDefinition) -> int:
    score = 0
    for keyword in group.keywords:
        normalized = _normalize_text(keyword)
        if normalized and normalized in text:
            score += 4 + min(len(normalized), 16)
    return score


def _profile_text(profile: LutStyleProfile) -> str:
    return _normalize_text(
        " ".join(
            [
                profile.id,
                profile.concept or "",
                profile.title or "",
                profile.metadata.originalFilename,
                profile.metadata.sourceUrl or "",
                " ".join(profile.derivedTags),
            ]
        )
    )


def classify_profile(profile: LutStyleProfile) -> str:
    text = _profile_text(profile)
    for group_id in CLASSIFICATION_PRIORITY:
        group = GROUP_BY_ID[group_id]
        if _score_group(text, group) > 0:
            return group_id

    scores = [(group.group_id, _score_group(text, group)) for group in STYLE_GROUPS]
    scores.sort(key=lambda item: item[1], reverse=True)
    if scores and scores[0][1] > 0:
        return scores[0][0]

    tags = set(profile.derivedTags)
    if "monochrome_like" in tags:
        return "monochrome"
    if "cinematic_split_tone" in tags:
        return "teal_orange"
    if "warm" in tags:
        return "warm_sunset"
    if "cool" in tags:
        return "cool_night"
    if "vibrant" in tags:
        return "vibrant_pop"
    if "muted" in tags or "soft_contrast" in tags:
        return "pastel_soft"
    return DEFAULT_GROUP_ID


def _clip(name: str, value: float) -> float:
    low, high = SLIDER_LIMITS[name]
    return max(low, min(high, value))


def _num(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _profile_slider_target(profile: LutStyleProfile) -> dict[str, float]:
    features = profile.features
    tone = features.get("tone", {})
    color = features.get("color_balance", {})
    saturation = features.get("saturation", {})

    contrast_delta = _num(tone.get("contrast_delta"))
    shadow_lift = _num(tone.get("shadow_lift"))
    midtone_lift = _num(tone.get("midtone_lift"))
    highlight_lift = _num(tone.get("highlight_lift"))
    black_point = _num(tone.get("black_point"))
    white_point = _num(tone.get("white_point"), 1.0)
    sat_delta = _num(saturation.get("mean_delta"))
    temp_shift = _num(color.get("temperature_shift"))
    tint_shift = _num(color.get("tint_shift"))

    return {
        "exposure": _clip("exposure", midtone_lift * 1.1),
        "contrast": _clip("contrast", contrast_delta * 145),
        "highlights": _clip("highlights", highlight_lift * 95),
        "shadows": _clip("shadows", shadow_lift * 95),
        "whites": _clip("whites", (white_point - 1.0) * 85 + highlight_lift * 25),
        "blacks": _clip("blacks", black_point * 80 + shadow_lift * 45),
        "temperature": _clip("temperature", temp_shift * 8500),
        "tint": _clip("tint", tint_shift * 220),
        "vibrance": _clip("vibrance", sat_delta * 150),
        "saturation": _clip("saturation", sat_delta * 95),
        "clarity": _clip("clarity", contrast_delta * 45),
        "texture": _clip("texture", contrast_delta * 28),
        "dehaze": _clip("dehaze", contrast_delta * 40),
    }


def _profile_hsl_target(profile: LutStyleProfile) -> dict[str, dict[str, float]]:
    probes = profile.features.get("color_probes", {})
    hsl: dict[str, dict[str, float]] = {}
    for color in HSL_COLORS:
        values = probes.get(color, {})
        hue = max(-12, min(12, _num(values.get("hue_shift_degrees")) / 4))
        saturation = max(-18, min(18, _num(values.get("saturation_delta")) * 55))
        luminance = max(-18, min(18, _num(values.get("luminance_delta")) * 70))
        if abs(hue) >= 0.4 or abs(saturation) >= 0.8 or abs(luminance) >= 0.8:
            hsl[color] = {
                "hue": round(hue, 2),
                "saturation": round(saturation, 2),
                "luminance": round(luminance, 2),
            }
    return hsl


def _weighted_average(values: list[tuple[float, float]]) -> float:
    total_weight = sum(weight for _, weight in values)
    if total_weight <= 0:
        return 0.0
    return sum(value * weight for value, weight in values) / total_weight


def _bounds_from_target(name: str, target: float) -> list[float]:
    half_width = PRIOR_HALF_WIDTH[name]
    low = _clip(name, target - half_width)
    high = _clip(name, target + half_width)
    return [round(low, 3), round(high, 3)]


def _aggregate_group(group_id: str, entries: list[tuple[LutStyleProfile, float]]) -> dict[str, Any]:
    definition = GROUP_BY_ID[group_id]
    slider_targets = {name: [] for name in SLIDER_LIMITS}
    hsl_targets: dict[str, dict[str, list[tuple[float, float]]]] = {
        color: {"hue": [], "saturation": [], "luminance": []} for color in HSL_COLORS
    }
    tag_counter: Counter[str] = Counter()
    source_counter: Counter[str] = Counter()

    for profile, weight in entries:
        tag_counter.update(profile.derivedTags)
        source_counter.update([_source_key(profile)])
        for name, value in _profile_slider_target(profile).items():
            slider_targets[name].append((value, weight))
        for color, values in _profile_hsl_target(profile).items():
            for channel, value in values.items():
                hsl_targets[color][channel].append((value, weight))

    slider_prior = {
        name: _bounds_from_target(name, _weighted_average(values))
        for name, values in slider_targets.items()
        if values
    }
    hsl_prior: dict[str, dict[str, float]] = {}
    for color, channels in hsl_targets.items():
        averaged = {
            channel: round(_weighted_average(values), 2)
            for channel, values in channels.items()
            if values
        }
        if averaged and any(abs(value) >= 0.4 for value in averaged.values()):
            hsl_prior[color] = averaged

    representative = sorted(
        (
            {
                "id": profile.id,
                "concept": profile.concept,
                "source": _source_key(profile),
                "weight": round(weight, 3),
            }
            for profile, weight in entries
        ),
        key=lambda item: (str(item["source"]), str(item["concept"])),
    )[:12]

    return {
        "id": group_id,
        "label": definition.label,
        "profileCount": len(entries),
        "effectiveWeight": round(sum(weight for _, weight in entries), 3),
        "keywords": list(definition.keywords),
        "mood": list(definition.mood),
        "targets": list(definition.targets),
        "avoid": list(definition.avoid),
        "sliderPrior": slider_prior,
        "hslPrior": hsl_prior,
        "topTags": [tag for tag, _ in tag_counter.most_common(8)],
        "topSources": [{"source": source, "count": count} for source, count in source_counter.most_common(6)],
        "representativeProfiles": representative,
    }


def _duplicate_summary(profiles: list[LutStyleProfile]) -> tuple[dict[str, float], dict[str, Any]]:
    by_hash: dict[str, list[LutStyleProfile]] = defaultdict(list)
    by_family: dict[str, list[LutStyleProfile]] = defaultdict(list)
    for profile in profiles:
        by_hash[profile.metadata.sha256].append(profile)
        by_family[_family_key(profile)].append(profile)

    family_groups = [items for items in by_family.values() if len(items) > 1]
    weights: dict[str, float] = {}
    for items in by_family.values():
        weight = 1.0 / len(items)
        for profile in items:
            weights[profile.id] = weight

    exact_hash_groups = [
        {
            "sha256": sha,
            "profileIds": sorted(profile.id for profile in items),
            "weightPerProfile": round(1.0 / len(items), 3),
        }
        for sha, items in sorted(by_hash.items())
        if len(items) > 1
    ]
    normalized_family_groups = [
        {
            "familyKey": _family_key(items[0]),
            "profileIds": sorted(profile.id for profile in items),
            "weightPerProfile": round(1.0 / len(items), 3),
        }
        for items in sorted(family_groups, key=lambda group: _family_key(group[0]))
    ]

    return weights, {
        "profileCount": len(profiles),
        "uniqueHashCount": len(by_hash),
        "exactHashDuplicateGroupCount": len(exact_hash_groups),
        "normalizedFamilyDuplicateGroupCount": len(normalized_family_groups),
        "exactHashGroups": exact_hash_groups[:80],
        "normalizedFamilyGroups": normalized_family_groups[:80],
    }


def build_lut_style_index(reference_root: Path | None = None) -> dict[str, Any]:
    root = reference_root or _reference_root()
    profiles = load_lut_style_profiles(root).items
    weights, duplicates = _duplicate_summary(profiles)
    grouped: dict[str, list[tuple[LutStyleProfile, float]]] = {group.group_id: [] for group in STYLE_GROUPS}
    for profile in profiles:
        group_id = classify_profile(profile)
        grouped[group_id].append((profile, weights.get(profile.id, 1.0)))

    groups = [
        _aggregate_group(group_id, entries)
        for group_id, entries in grouped.items()
        if entries
    ]
    groups.sort(key=lambda group: (-group["profileCount"], group["id"]))
    return {
        "version": 1,
        "kind": "lut_style_index",
        "profileCount": len(profiles),
        "groupCount": len(groups),
        "duplicates": duplicates,
        "groups": groups,
    }


def style_index_path(reference_root: Path | None = None) -> Path:
    root = reference_root or _reference_root()
    return root / "luts" / "style_index.json"


def save_lut_style_index(reference_root: Path | None = None) -> dict[str, Any]:
    root = reference_root or _reference_root()
    index = build_lut_style_index(root)
    path = style_index_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    return index


def load_lut_style_index(reference_root: Path | None = None) -> dict[str, Any]:
    path = style_index_path(reference_root)
    if not path.exists():
        raise LutAnalysisError(f"Missing LUT style index: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise LutAnalysisError(f"Cannot read LUT style index: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LutAnalysisError(f"Invalid LUT style index JSON: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("kind") != "lut_style_index":
        raise LutAnalysisError("Invalid LUT style index payload")
    return payload


def match_lut_style_prior(style_prompt: str, *, style_id: str | None = None, reference_root: Path | None = None) -> dict[str, Any] | None:
    try:
        index = load_lut_style_index(reference_root)
    except LutAnalysisError:
        return None

    prompt = _normalize_text(style_prompt)
    if not prompt:
        return None
    style_hints = STYLE_ID_GROUP_HINTS.get(style_id or "", {})

    best: dict[str, Any] | None = None
    best_score = 0
    for group in index.get("groups", []):
        if not isinstance(group, dict):
            continue
        text_bits = [group.get("id", ""), group.get("label", ""), " ".join(group.get("keywords", []))]
        group_text = _normalize_text(" ".join(str(bit) for bit in text_bits))
        score = 0
        hit_count = 0
        for token in prompt.split():
            if len(token) >= 3 and token in group_text:
                score += 2 + min(len(token), 10)
        for keyword in group.get("keywords", []):
            normalized = _normalize_text(str(keyword))
            if normalized and normalized in prompt:
                score += 6 + min(len(normalized), 16)
                hit_count += 1
        group_id = str(group.get("id", ""))
        score += style_hints.get(group_id, 0)
        for keyword in EXPLICIT_GROUP_BOOSTS.get(group_id, ()):
            normalized = _normalize_text(keyword)
            if normalized and normalized in prompt:
                score += 24
                break
        if group_id == "teal_orange" and "teal" in prompt and "orange" in prompt:
            score += 30
        if group_id == "panasonic_rec709" and ("rec709" in prompt or "v709" in prompt) and ("panasonic" in prompt or "lumix" in prompt):
            score += 24
        if hit_count >= 2:
            score += hit_count * 8
        if score > best_score:
            best_score = score
            best = group

    if best is None or best_score <= 0:
        return None
    return {**best, "matchScore": float(best_score)}
