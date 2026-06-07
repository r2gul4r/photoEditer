import numpy as np

from app.services.image_analysis import analyze_rgb_array
from app.services.reference_style_target import build_reference_style_target
from app.services.style_interpreter import interpret_style


def test_cool_japanese_summer_target_uses_daylight_reference_constraints() -> None:
    analysis = analyze_rgb_array(np.full((48, 48, 3), 0.48, dtype=np.float32))
    style = interpret_style("cool Japanese summer")

    target = build_reference_style_target(analysis, style)
    groups = {signal.group_id for signal in target.reference_groups}

    assert "pastel_soft" in groups
    assert "cool_night" not in groups
    assert "avoid_global_blue_wash" in target.constraints.hard
    assert "avoid_cool_night" in target.constraints.hard
    assert target.mood_axes["daylight"] == 1.0
    assert target.slider_bounds["temperature"][0] >= -340
    assert target.slider_bounds["saturation"][1] <= 3


def test_reference_style_target_tightens_source_risk_bounds() -> None:
    bright = np.full((48, 48, 3), 0.98, dtype=np.float32)
    analysis = analyze_rgb_array(bright)
    style = interpret_style("clean instagram")

    target = build_reference_style_target(analysis, style)

    assert "avoid_extra_exposure" in target.constraints.hard
    assert target.slider_bounds["exposure"][1] <= 0.08
    assert target.slider_bounds["highlights"][1] <= -16
