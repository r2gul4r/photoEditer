from app.services.codex_app_server import _extract_json


def test_extract_json_uses_first_object_when_codex_stream_duplicates_text() -> None:
    payload = '{"message":"ok","candidates":[]}'

    assert _extract_json(payload + payload) == {"message": "ok", "candidates": []}


def test_extract_json_ignores_wrapping_text() -> None:
    assert _extract_json('prefix {"message":"ok","candidates":[]} suffix') == {"message": "ok", "candidates": []}
