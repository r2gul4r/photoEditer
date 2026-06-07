from app.services.style_interpreter import interpret_style


def test_cool_japanese_summer_prompt() -> None:
    style = interpret_style("시원한 일본 여름 느낌")

    assert style.style_id == "cool_japanese_summer"
    assert "cool" in style.mood
    assert "low-key" not in style.mood
    assert style.lut_style_group != "cool_night"
    assert style.preset_style_group != "cool_night"
    assert style.slider_prior["temperature"][0] >= -420
    assert "flat blue cast" in style.avoid


def test_animation_prompt() -> None:
    style = interpret_style("animation 느낌")

    assert style.style_id == "anime_background"


def test_film_prompt_priority() -> None:
    style = interpret_style("청량한 필름톤")

    assert style.style_id == "soft_film"


def test_cinematic_color_grading_prompts_map_to_cinematic_style() -> None:
    style = interpret_style("암부에 파란빛 돌고 틸앤오렌지 느낌")

    assert style.style_id == "cinematic_mood"
    assert style.lut_style_group == "teal_orange"
    assert "blue shadows" in style.targets

