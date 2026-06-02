from app.services.style_interpreter import interpret_style


def test_cool_japanese_summer_prompt() -> None:
    style = interpret_style("시원한 일본 여름 느낌")

    assert style.style_id == "cool_japanese_summer"
    assert "cool" in style.mood


def test_animation_prompt() -> None:
    style = interpret_style("animation 느낌")

    assert style.style_id == "anime_background"


def test_film_prompt_priority() -> None:
    style = interpret_style("청량한 필름톤")

    assert style.style_id == "soft_film"

