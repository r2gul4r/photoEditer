from app.services.lut_style_index import load_lut_style_index, match_lut_style_prior
from app.services.style_interpreter import interpret_style


def test_lut_style_index_groups_profiles_and_duplicates() -> None:
    index = load_lut_style_index()

    assert index["profileCount"] == 300
    assert index["groupCount"] >= 8
    assert index["duplicates"]["uniqueHashCount"] <= 300
    wedding = next(group for group in index["groups"] if group["id"] == "wedding_warm")
    assert wedding["profileCount"] >= 20
    assert "temperature" in wedding["sliderPrior"]
    assert wedding["hslPrior"]


def test_lut_style_match_uses_prompt_keywords() -> None:
    match = match_lut_style_prior("warm wedding lumix skin")

    assert match is not None
    assert match["id"] == "wedding_warm"
    assert match["profileCount"] >= 20


def test_style_interpreter_blends_lut_prior_for_matching_prompt() -> None:
    style = interpret_style("warm wedding lumix skin")

    assert style.lut_style_group == "wedding_warm"
    assert style.lut_profile_count >= 20
    assert style.lut_hsl_prior
