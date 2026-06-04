import numpy as np

from app.services.image_analysis import analyze_rgb_array
from app.services.recommendation_engine import generate_recommendations
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
