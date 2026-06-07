from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any

from app.models.schemas import PresetStyleProfile
from app.services.lut_style_index import GROUP_BY_ID, STYLE_GROUPS
from app.services.preset_analysis import PresetAnalysisError, load_preset_style_profiles


SLIDER_HALF_WIDTH: dict[str, float] = {
    "exposure": 0.12,
    "contrast": 8,
    "highlights": 10,
    "shadows": 10,
    "whites": 8,
    "blacks": 8,
    "temperature": 240,
    "tint": 6,
    "vibrance": 7,
    "saturation": 7,
    "clarity": 6,
    "texture": 5,
    "dehaze": 6,
}

TONE_KEYS = ("exposure", "contrast", "highlights", "shadows", "whites", "blacks", "clarity", "texture", "dehaze")
COLOR_KEYS = ("temperature", "tint", "vibrance", "saturation")
HSL_COLORS = ("red", "orange", "yellow", "green", "aqua", "blue", "purple", "magenta")
GROUP_PRIORITY = (
    "wedding_warm",
    "beauty_skin",
    "monochrome",
    "teal_orange",
    "cool_night",
    "warm_sunset",
    "film_vintage",
    "pastel_soft",
    "vibrant_pop",
    "clean_natural",
    "cinematic_mood",
)

STYLE_ID_GROUP_HINTS: dict[str, dict[str, int]] = {
    "soft_film": {"film_vintage": 12, "pastel_soft": 8},
    "cool_japanese_summer": {"pastel_soft": 24, "clean_natural": 12, "cool_night": -8},
    "anime_background": {"pastel_soft": 8, "vibrant_pop": 4},
    "warm_cafe": {"warm_sunset": 10},
    "cinematic_mood": {"cinematic_mood": 10, "teal_orange": 4},
    "clean_instagram": {"clean_natural": 6},
}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _reference_root() -> Path:
    return _project_root() / "reference"


def _index_path(reference_root: Path) -> Path:
    return reference_root / "presets" / "style_index.json"


def _normalize_text(value: str | None) -> str:
    return re.sub(r"[^a-z0-9\uac00-\ud7a3]+", " ", (value or "").casefold()).strip()


def _family_key(profile: PresetStyleProfile) -> str:
    text = _normalize_text(f"{profile.concept or ''} {profile.title or ''}")
    text = re.sub(r"\b(free|preset|lightroom|xmp|dng|lrtemplate|desktop|mobile|pack|collection)\b", " ", text)
    text = re.sub(r"\b[0-9]+\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or profile.metadata.sha256[:12]


def _profile_text(profile: PresetStyleProfile) -> str:
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


def _score_group(text: str, group_id: str) -> int:
    group = GROUP_BY_ID[group_id]
    score = 0
    for keyword in group.keywords:
        normalized = _normalize_text(keyword)
        if normalized and normalized in text:
            score += 6 + min(len(normalized), 18)
    return score


def classify_preset_profile(profile: PresetStyleProfile) -> str:
    text = _profile_text(profile)
    tags = set(profile.derivedTags)
    tag_map = {
        "wedding": "wedding_warm",
        "beauty": "beauty_skin",
        "monochrome": "monochrome",
        "teal_orange": "teal_orange",
        "cool": "cool_night",
        "warm": "warm_sunset",
        "film": "film_vintage",
        "pastel": "pastel_soft",
        "vibrant": "vibrant_pop",
        "clean": "clean_natural",
        "cinematic": "cinematic_mood",
    }
    for tag in ("wedding", "beauty", "monochrome", "teal_orange"):
        if tag in tags:
            return tag_map[tag]
    scores = [(group_id, _score_group(text, group_id)) for group_id in GROUP_PRIORITY]
    for tag, group_id in tag_map.items():
        if tag in tags:
            scores.append((group_id, 18))
    scores.sort(key=lambda item: item[1], reverse=True)
    if scores and scores[0][1] > 0:
        return scores[0][0]
    sliders = profile.features.get("sliderAdjustments", {})
    if isinstance(sliders, dict):
        if float(sliders.get("temperature", 0) or 0) > 250:
            return "warm_sunset"
        if float(sliders.get("temperature", 0) or 0) < -250:
            return "cool_night"
        if float(sliders.get("saturation", 0) or 0) < -25:
            return "monochrome"
    return "cinematic_mood"


def _weighted_values(entries: list[tuple[PresetStyleProfile, float]], key: str) -> list[float]:
    values: list[float] = []
    for profile, weight in entries:
        sliders = profile.features.get("sliderAdjustments", {})
        if not isinstance(sliders, dict) or key not in sliders:
            continue
        repeat = max(1, round(weight * 4))
        values.extend([float(sliders[key])] * repeat)
    return values


def _weighted_median(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(float(median(values)), 3)


def _slider_prior(entries: list[tuple[PresetStyleProfile, float]]) -> dict[str, list[float]]:
    prior: dict[str, list[float]] = {}
    for key, half_width in SLIDER_HALF_WIDTH.items():
        values = _weighted_values(entries, key)
        if not values:
            continue
        center = _weighted_median(values)
        sorted_values = sorted(values)
        q1 = sorted_values[len(sorted_values) // 4]
        q3 = sorted_values[(len(sorted_values) * 3) // 4]
        spread = max(half_width, abs(q3 - q1) / 2)
        prior[key] = [round(center - spread, 3), round(center + spread, 3)]
    return prior


def _flat_prior(entries: list[tuple[PresetStyleProfile, float]], keys: tuple[str, ...]) -> dict[str, float]:
    return {key: _weighted_median(_weighted_values(entries, key)) for key in keys if _weighted_values(entries, key)}


def _hsl_prior(entries: list[tuple[PresetStyleProfile, float]]) -> dict[str, dict[str, float]]:
    prior: dict[str, dict[str, float]] = {}
    for color in HSL_COLORS:
        color_values: dict[str, float] = {}
        for channel in ("hue", "saturation", "luminance"):
            values: list[float] = []
            for profile, weight in entries:
                hsl = profile.features.get("hslAdjustments", {})
                if not isinstance(hsl, dict):
                    continue
                adjustment = hsl.get(color, {})
                if not isinstance(adjustment, dict) or channel not in adjustment:
                    continue
                values.extend([float(adjustment[channel])] * max(1, round(weight * 4)))
            if values:
                color_values[channel] = _weighted_median(values)
        if color_values:
            prior[color] = color_values
    return prior


def _grading_prior(entries: list[tuple[PresetStyleProfile, float]]) -> dict[str, dict[str, float]]:
    prior: dict[str, dict[str, float]] = {}
    for zone in ("shadows", "midtones", "highlights", "global"):
        zone_values: dict[str, float] = {}
        for channel in ("hue", "sat", "lum", "saturation"):
            values: list[float] = []
            for profile, weight in entries:
                grading = profile.features.get("colorGrading", {})
                if not isinstance(grading, dict):
                    continue
                adjustment = grading.get(zone, {})
                if not isinstance(adjustment, dict) or channel not in adjustment:
                    continue
                values.extend([float(adjustment[channel])] * max(1, round(weight * 4)))
            if values:
                zone_values[channel] = _weighted_median(values)
        if zone_values:
            prior[zone] = zone_values
    return prior


def _risk_notes(group_id: str, entries: list[tuple[PresetStyleProfile, float]]) -> list[str]:
    notes = list(GROUP_BY_ID[group_id].avoid)
    slider_prior = _flat_prior(entries, tuple(SLIDER_HALF_WIDTH))
    if abs(slider_prior.get("temperature", 0)) > 700:
        notes.append("strong white-balance shift can fight the source image")
    if slider_prior.get("contrast", 0) > 25 or slider_prior.get("blacks", 0) < -25:
        notes.append("high contrast presets can crush shadow detail")
    if slider_prior.get("saturation", 0) > 25 or slider_prior.get("vibrance", 0) > 30:
        notes.append("strong saturation may overshoot skin and foliage")
    if slider_prior.get("saturation", 0) < -30:
        notes.append("heavy desaturation may remove intended color cues")
    seen: list[str] = []
    for note in notes:
        if note and note not in seen:
            seen.append(note)
    return seen


def _duplicate_summary(profiles: list[PresetStyleProfile]) -> dict[str, Any]:
    by_hash: dict[str, list[str]] = defaultdict(list)
    by_family: dict[str, list[str]] = defaultdict(list)
    for profile in profiles:
        by_hash[profile.metadata.sha256].append(profile.id)
        by_family[_family_key(profile)].append(profile.id)
    exact = [
        {"sha256": sha, "profileIds": ids, "weightPerProfile": round(1 / len(ids), 3)}
        for sha, ids in sorted(by_hash.items())
        if len(ids) > 1
    ]
    family = [
        {"familyKey": key, "profileIds": ids, "weightPerProfile": round(1 / len(ids), 3)}
        for key, ids in sorted(by_family.items())
        if len(ids) > 1
    ]
    return {
        "profileCount": len(profiles),
        "uniqueHashCount": len(by_hash),
        "exactHashDuplicateGroupCount": len(exact),
        "normalizedFamilyDuplicateGroupCount": len(family),
        "exactHashGroups": exact[:25],
        "normalizedFamilyGroups": family[:25],
    }


def build_preset_style_index(reference_root: Path | None = None) -> dict[str, Any]:
    root = reference_root or _reference_root()
    profiles = load_preset_style_profiles(root).items
    duplicates = _duplicate_summary(profiles)
    exact_counts = Counter(profile.metadata.sha256 for profile in profiles)
    grouped: dict[str, list[tuple[PresetStyleProfile, float]]] = defaultdict(list)
    profile_group_ids: dict[str, str] = {}
    for profile in profiles:
        weight = 1 / exact_counts[profile.metadata.sha256]
        group_id = classify_preset_profile(profile)
        profile_group_ids[profile.id] = group_id
        grouped[group_id].append((profile, weight))

    groups: list[dict[str, Any]] = []
    for group_id, entries in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        definition = GROUP_BY_ID[group_id]
        tag_counts = Counter(tag for profile, _ in entries for tag in profile.derivedTags)
        source_counts = Counter(_normalize_text(profile.metadata.sourceUrl or "") for profile, _ in entries)
        group = {
            "id": group_id,
            "label": definition.label,
            "profileCount": len(entries),
            "effectiveWeight": round(sum(weight for _, weight in entries), 3),
            "promptKeywords": list(definition.keywords),
            "mood": list(definition.mood),
            "targets": list(definition.targets),
            "avoid": list(definition.avoid),
            "riskNotes": _risk_notes(group_id, entries),
            "sliderPrior": _slider_prior(entries),
            "tonePrior": _flat_prior(entries, TONE_KEYS),
            "colorBalancePrior": _flat_prior(entries, COLOR_KEYS),
            "hslPrior": _hsl_prior(entries),
            "colorGradingPrior": _grading_prior(entries),
            "topTags": [tag for tag, _ in tag_counts.most_common(12)],
            "topSources": [
                {"source": source or "unknown", "count": count}
                for source, count in source_counts.most_common(8)
            ],
            "representativeProfiles": [
                {
                    "id": profile.id,
                    "title": profile.title,
                    "concept": profile.concept,
                    "source": profile.metadata.sourceUrl,
                    "weight": round(weight, 3),
                }
                for profile, weight in entries[:12]
            ],
        }
        groups.append(group)

    return {
        "version": 1,
        "kind": "lightroom_preset_style_index",
        "profileCount": len(profiles),
        "groupCount": len(groups),
        "duplicates": duplicates,
        "selectionBasis": "Public/free Lightroom preset pages; original preset files deleted after low-dimensional profile extraction.",
        "analyzedProfiles": [
            {
                "id": profile.id,
                "title": profile.title,
                "concept": profile.concept,
                "source": profile.metadata.sourceUrl,
                "format": profile.format,
                "groupId": profile_group_ids.get(profile.id),
                "derivedTags": profile.derivedTags,
            }
            for profile in sorted(
                profiles,
                key=lambda item: (
                    item.metadata.importedAt or "",
                    item.metadata.sourceUrl or "",
                    item.title or "",
                ),
            )
        ],
        "groups": groups,
    }


def save_preset_style_index(reference_root: Path | None = None) -> dict[str, Any]:
    root = reference_root or _reference_root()
    index = build_preset_style_index(root)
    path = _index_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


def load_preset_style_index(reference_root: Path | None = None) -> dict[str, Any]:
    root = reference_root or _reference_root()
    path = _index_path(root)
    if not path.exists():
        raise PresetAnalysisError(f"Preset style index does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PresetAnalysisError(f"Invalid preset style index: {path}") from exc
    if not isinstance(payload, dict) or payload.get("kind") != "lightroom_preset_style_index":
        raise PresetAnalysisError("Invalid Lightroom preset style index payload")
    return payload


def match_preset_style_prior(style_prompt: str, *, style_id: str | None = None, reference_root: Path | None = None) -> dict[str, Any] | None:
    try:
        index = load_preset_style_index(reference_root)
    except PresetAnalysisError:
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
        group_id = str(group.get("id", ""))
        keywords = group.get("promptKeywords", [])
        group_text = _normalize_text(" ".join([group_id, str(group.get("label", "")), " ".join(str(k) for k in keywords)]))
        group_words = set(group_text.split())
        score = style_hints.get(group_id, 0)
        for token in prompt.split():
            if len(token) >= 3 and token in group_words:
                score += 2 + min(len(token), 10)
        for keyword in keywords:
            normalized = _normalize_text(str(keyword))
            if normalized and normalized in prompt:
                score += 8 + min(len(normalized), 18)
        if group_id == "teal_orange" and "teal" in prompt and "orange" in prompt:
            score += 30
        if group_id == "wedding_warm" and ("wedding" in prompt or "bridal" in prompt):
            score += 24
        if group_id == "beauty_skin" and any(token in prompt for token in ("portrait", "skin", "skintone", "beauty", "newborn")):
            score += 24
        if group_id == "clean_natural" and any(token in prompt for token in ("clean", "natural", "product", "real estate", "interior")):
            score += 18
        if group_id == "monochrome" and ("black" in prompt and "white" in prompt):
            score += 24
        if score > best_score:
            best_score = score
            best = group
    if best is None or best_score <= 0:
        return None
    return {**best, "matchScore": float(best_score)}
