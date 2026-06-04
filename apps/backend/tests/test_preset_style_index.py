from app.services.preset_style_index import load_preset_style_index, match_preset_style_prior
from app.services.style_interpreter import interpret_style


def test_preset_style_index_groups_public_presets() -> None:
    index = load_preset_style_index()

    assert index["profileCount"] >= 100
    assert index["groupCount"] >= 8
    assert index["duplicates"]["uniqueHashCount"] <= index["profileCount"]
    assert len(index["analyzedProfiles"]) == index["profileCount"]
    assert all(profile["source"] for profile in index["analyzedProfiles"])
    assert any("editingfree.com" in profile["source"] for profile in index["analyzedProfiles"])
    assert any(group["id"] == "wedding_warm" for group in index["groups"])
    assert any(group["sliderPrior"] for group in index["groups"])


def test_preset_style_match_uses_prompt_keywords() -> None:
    match = match_preset_style_prior("warm wedding preset")

    assert match is not None
    assert match["id"] == "wedding_warm"
    assert match["profileCount"] >= 1


def test_style_interpreter_blends_preset_prior_for_matching_prompt() -> None:
    style = interpret_style("cinematic teal orange preset")

    assert style.preset_style_group in {"teal_orange", "cinematic_mood"}
    assert style.preset_profile_count >= 1
