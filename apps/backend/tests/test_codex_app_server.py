import json

from app.services.codex_app_server import COMPACT_VECTOR_LENGTH, _extract_json, _parse_candidates


def test_extract_json_uses_first_object_when_codex_stream_duplicates_text() -> None:
    payload = '{"message":"ok","candidates":[]}'

    assert _extract_json(payload + payload) == {"message": "ok", "candidates": []}


def test_extract_json_ignores_wrapping_text() -> None:
    assert _extract_json('prefix {"message":"ok","candidates":[]} suffix') == {"message": "ok", "candidates": []}


def test_parse_compact_candidates_expands_vectors() -> None:
    vector = [0] * COMPACT_VECTOR_LENGTH
    vector[0] = 3
    vector[1] = -250
    vector[6] = -3000
    vector[13] = -125
    vector[14] = 24
    vector[15] = 140
    payload = {
        "m": "compact ok",
        "c": {
            "n": vector,
            "s": [1] * COMPACT_VECTOR_LENGTH,
            "b": [-1] * COMPACT_VECTOR_LENGTH,
        },
        "w": {"n": ["check highlights"]},
    }

    result = _parse_candidates(json.dumps(payload))

    assert result.message == "compact ok"
    assert [candidate.id for candidate in result.candidates] == ["natural", "style", "bold"]
    natural = result.candidates[0]
    assert natural.name == "Natural"
    assert natural.adjustments.exposure == 2
    assert natural.adjustments.contrast == -100
    assert natural.adjustments.temperature == -2000
    assert natural.adjustments.hsl["red"].hue == -100
    assert natural.adjustments.hsl["red"].saturation == 24
    assert natural.adjustments.hsl["red"].luminance == 100
    assert natural.warnings == ["check highlights"]


def test_parse_legacy_candidates_still_works() -> None:
    payload = {
        "message": "legacy ok",
        "candidates": [
            {"id": "natural", "name": "N", "description": "n", "adjustments": {}, "score": 0.9, "warnings": []},
            {"id": "style", "name": "S", "description": "s", "adjustments": {}, "score": 0.8, "warnings": []},
            {"id": "bold", "name": "B", "description": "b", "adjustments": {}, "score": 0.7, "warnings": []},
        ],
    }

    result = _parse_candidates(json.dumps(payload))

    assert result.message == "legacy ok"
    assert [candidate.name for candidate in result.candidates] == ["N", "S", "B"]
