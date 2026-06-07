from pathlib import Path

import numpy as np
from PIL import Image

from app.services.image_analysis import analyze_image, analyze_rgb_array
from app.services.recommendation_engine import build_candidate_bank, generate_recommendations
from app.services.reference_style_target import build_reference_style_target
from app.services.renderer import render_preview
from app.services.scene_interpreter import interpret_scene
from app.services.style_interpreter import interpret_style


def test_recommendations_always_include_three_candidates() -> None:
    analysis = analyze_rgb_array(np.full((48, 48, 3), 0.48, dtype=np.float32))
    style = interpret_style("시원한 일본 여름 느낌")

    candidates = generate_recommendations(analysis, style, strength=0.7)

    assert [candidate.id for candidate in candidates] == ["natural", "style", "bold"]
    assert all(candidate.adjustments for candidate in candidates)


def test_highlight_risk_limits_candidate_exposure() -> None:
    analysis = analyze_rgb_array(np.ones((48, 48, 3), dtype=np.float32))
    style = interpret_style("깨끗한 인스타그램톤")

    candidates = generate_recommendations(analysis, style, strength=1)

    assert candidates[0].adjustments.exposure <= 0.12
    assert candidates[0].adjustments.highlights <= -28
    assert candidates[0].warnings


def test_lut_style_index_prior_affects_hsl_adjustments() -> None:
    analysis = analyze_rgb_array(np.full((48, 48, 3), 0.48, dtype=np.float32))
    style = interpret_style("cinematic teal orange")

    candidates = generate_recommendations(analysis, style, strength=0.8)

    assert style.lut_style_group == "teal_orange"
    assert style.lut_profile_count > 0
    assert candidates[1].adjustments.hsl


def test_teal_orange_prompt_adds_split_color_grading() -> None:
    analysis = analyze_rgb_array(np.full((48, 48, 3), 0.48, dtype=np.float32))
    style = interpret_style("틸앤오렌지 시네마틱")

    candidates = generate_recommendations(analysis, style, strength=0.8)
    grading = candidates[1].adjustments.color_grading

    assert style.lut_style_group == "teal_orange"
    assert grading.shadows.saturation > 6
    assert 195 <= grading.shadows.hue <= 220
    assert grading.highlights.saturation > 4
    assert 30 <= grading.highlights.hue <= 45
    assert "암부 hue" in (candidates[1].color_summary or "")


def test_cool_japanese_summer_uses_targeted_color_not_blue_wash() -> None:
    analysis = analyze_rgb_array(np.full((48, 48, 3), 0.48, dtype=np.float32))
    style = interpret_style("cool Japanese summer")

    candidates = generate_recommendations(analysis, style, strength=0.7)
    style_adjustments = candidates[1].adjustments

    assert style.lut_style_group != "cool_night"
    assert style_adjustments.temperature >= -240
    assert style_adjustments.saturation <= 3
    assert style_adjustments.hsl["blue"].luminance >= 6
    assert style_adjustments.hsl["green"].saturation > 0
    assert style_adjustments.dehaze <= 0


def test_cool_japanese_summer_warm_cast_cooling_stays_moderate() -> None:
    warm = np.zeros((48, 48, 3), dtype=np.float32)
    warm[..., 0] = 0.62
    warm[..., 1] = 0.48
    warm[..., 2] = 0.38
    analysis = analyze_rgb_array(warm)
    style = interpret_style("cool Japanese summer")

    candidates = generate_recommendations(analysis, style, strength=0.7)

    assert analysis.risk_flags.strong_warm_cast
    assert candidates[1].adjustments.temperature >= -220


def test_recommendations_score_rendered_source_without_blue_wash(monkeypatch) -> None:
    warm = np.zeros((96, 128, 3), dtype=np.float32)
    warm[..., 0] = 0.62
    warm[..., 1] = 0.5
    warm[..., 2] = 0.38
    warm[:42, :, 2] = 0.66
    warm[:42, :, 1] = 0.58
    image = Image.fromarray((warm * 255).astype(np.uint8), mode="RGB")
    analysis = analyze_image(image)
    style = interpret_style("cool Japanese summer")
    monkeypatch.setattr(
        "app.services.recommendation_engine._load_source_image",
        lambda source_path, file_type: image,
    )

    candidates = generate_recommendations(analysis, style, strength=0.8, source_path=Path("in-memory.jpg"), file_type="jpeg")
    style_candidate = candidates[1]
    preview = render_preview(image, style_candidate.adjustments, max_side=128)
    preview_analysis = analyze_image(preview)

    assert "레퍼런스(" in (style_candidate.risk_summary or "")
    assert "scene:" in (style_candidate.risk_summary or "")
    assert style_candidate.adjustments.temperature >= -220
    assert style_candidate.adjustments.saturation <= 3
    assert not preview_analysis.risk_flags.strong_cool_cast


def test_preview_scoring_errors_are_reported(monkeypatch) -> None:
    image = Image.new("RGB", (96, 96), (120, 140, 160))
    analysis = analyze_image(image)
    style = interpret_style("clean instagram")
    monkeypatch.setattr(
        "app.services.recommendation_engine._load_source_image",
        lambda source_path, file_type: image,
    )

    def broken_preview(*args, **kwargs):
        raise RuntimeError("render failed")

    monkeypatch.setattr("app.services.recommendation_engine.render_preview", broken_preview)

    candidates = generate_recommendations(analysis, style, strength=0.7, source_path=Path("in-memory.jpg"), file_type="jpeg")

    assert any("프리뷰 점수 계산을 건너뛰었어" in warning for warning in candidates[1].warnings)


def test_candidate_bank_adds_scene_specific_non_destructive_options() -> None:
    arr = np.zeros((96, 128, 3), dtype=np.uint8)
    arr[:42, :, :] = [92, 166, 225]
    arr[42:, :, :] = [74, 130, 72]
    arr[54:80, 24:50, :] = [198, 132, 94]
    image = Image.fromarray(arr, mode="RGB")
    analysis = analyze_image(image)
    style = interpret_style("cool Japanese summer")
    target = build_reference_style_target(analysis, style)
    scene = interpret_scene(image)

    bank = build_candidate_bank(style, target, strength=0.8, scene=scene)
    style_sources = {option.source for option in bank["style"]}

    assert len(bank["style"]) >= 7
    assert "scene_sky_protect" in style_sources
    assert "scene_foliage_fresh" in style_sources
    assert "scene_skin_protect" in style_sources
