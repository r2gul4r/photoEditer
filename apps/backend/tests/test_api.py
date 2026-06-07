import io

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.models.schemas import AiConnectionStatus
from app.config import settings
from app.routers import ai as ai_router
from app.routers import recommend as recommend_router
from app.services.ai_preview_judge import PreviewJudgeResult
from app.services.codex_app_server import CodexRecommendationError, CodexRecommendationResult
from app.services.recommendation_engine import generate_recommendations


def _jpeg_bytes() -> bytes:
    image = Image.new("RGB", (96, 64), (110, 145, 190))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def _reference_jpeg_bytes(shadow_color: tuple[int, int, int], highlight_color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (96, 64), shadow_color)
    for x in range(48, 96):
        for y in range(64):
            image.putpixel((x, y), highlight_color)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def _fake_judge_result(**kwargs) -> PreviewJudgeResult:
    candidates = kwargs["candidates"]
    judged = [
        candidate.model_copy(
            update={
                "score": 0.95 if candidate.id == "style" else candidate.score,
                "risk_summary": f"{candidate.risk_summary} / AI judge 0.95: fake preview evaluation",
            },
            deep=True,
        )
        for candidate in candidates
    ]
    return PreviewJudgeResult(candidates=judged, message="fake preview judge", best_id="style", reviews={})


def test_api_analyze_recommend_preview_and_export_flow() -> None:
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["ok"] is True

    analyze = client.post(
        "/api/images/analyze",
        files={"file": ("smoke.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert analyze.status_code == 200
    analyzed = analyze.json()
    assert analyzed["file_type"] == "jpeg"
    assert analyzed["width"] == 96
    assert analyzed["height"] == 64
    assert analyzed["source_preview_url"].startswith("/api/previews/")
    source_preview = client.get(analyzed["source_preview_url"])
    assert source_preview.status_code == 200
    assert source_preview.headers["content-type"] == "image/jpeg"

    recommend = client.post(
        "/api/recommend",
        json={
            "image_id": analyzed["image_id"],
            "style_prompt": "\uc2dc\uc6d0\ud55c \uc77c\ubcf8 \uc5ec\ub984 \ub290\ub08c",
            "strength": 0.7,
            "ai_mode": "rules",
        },
    )
    assert recommend.status_code == 200
    recommendation = recommend.json()
    assert recommendation["style_interpretation"]["style_id"] == "cool_japanese_summer"
    assert [candidate["id"] for candidate in recommendation["candidates"]] == ["natural", "style", "bold"]
    assert recommendation["ai_status"]["provider"] == "rules"
    assert recommendation["ai_status"]["status"] == "not_requested"

    candidate = recommendation["candidates"][0]
    assert candidate["intent"]
    assert candidate["tone_summary"]
    assert candidate["color_summary"]
    assert candidate["risk_summary"]
    preview = client.post(
        "/api/preview",
        json={
            "image_id": analyzed["image_id"],
            "candidate_id": candidate["id"],
            "adjustments": candidate["adjustments"],
        },
    )
    assert preview.status_code == 200
    assert preview.json()["preview_url"].startswith("/api/previews/")

    export = client.post(
        "/api/export/preset-json",
        json={
            "image_id": analyzed["image_id"],
            "style_prompt": "\uc2dc\uc6d0\ud55c \uc77c\ubcf8 \uc5ec\ub984 \ub290\ub08c",
            "candidate": candidate,
        },
    )
    assert export.status_code == 200
    assert export.json()["candidate"]["id"] == "natural"

    rendered_export = client.post(
        "/api/export/rendered-image",
        json={
            "image_id": analyzed["image_id"],
            "candidate_id": candidate["id"],
            "adjustments": candidate["adjustments"],
            "format": "jpeg",
        },
    )
    assert rendered_export.status_code == 200
    assert rendered_export.headers["content-type"] == "image/jpeg"
    assert rendered_export.content.startswith(b"\xff\xd8")


def test_ai_status_reports_codex_connection(monkeypatch) -> None:
    client = TestClient(app)

    def fake_probe() -> AiConnectionStatus:
        return AiConnectionStatus(
            provider="codex-app-server",
            available=True,
            command="codex",
            message="fake initialized",
            user_agent="codex-test",
            platform="windows",
        )

    monkeypatch.setattr(ai_router, "probe_codex_app_server", fake_probe)

    response = client.get("/api/ai/status")
    body = response.json()
    assert response.status_code == 200
    assert body["provider"] == "codex-app-server"
    assert body["available"] is True
    assert body["command"] == "codex"
    assert body["user_agent"] == "codex-test"


def test_reference_library_lists_example_manifest() -> None:
    client = TestClient(app)

    response = client.get("/api/references")
    body = response.json()
    assert response.status_code == 200
    assert body["root"] == "reference"
    assert body["count"] >= 1
    example = next(item for item in body["items"] if item["id"] == "example-reference-001")
    assert example["manifest_path"] == "manifests/example.json"
    assert example["source"]["path"] == "raw/example.dng"
    assert example["source"]["exists"] is False
    assert example["targets"][0]["style"] == "clean-natural"
    assert example["preset"]["adjustments"]["exposure"] == 0


def test_style_reference_uploads_can_drive_recommendations() -> None:
    client = TestClient(app)
    analyze = client.post(
        "/api/images/analyze",
        files={"file": ("smoke.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    analyzed = analyze.json()

    upload = client.post(
        "/api/references/style-targets",
        files=[
            ("files", ("ref-a.jpg", _reference_jpeg_bytes((32, 54, 112), (220, 174, 104)), "image/jpeg")),
            ("files", ("ref-b.jpg", _reference_jpeg_bytes((28, 48, 96), (210, 168, 96)), "image/jpeg")),
        ],
    )
    assert upload.status_code == 200
    reference = upload.json()["reference"]
    assert reference["count"] == 2
    assert reference["shadow_blue_bias"] > 0
    assert reference["color_grading"]["shadows"]["saturation"] > 0

    response = client.post(
        "/api/recommend",
        json={
            "image_id": analyzed["image_id"],
            "style_prompt": "비슷한 느낌으로",
            "strength": 0.7,
            "ai_mode": "rules",
            "style_reference_id": reference["style_reference_id"],
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert "사용자 레퍼런스" in body["candidates"][1]["risk_summary"]
    assert body["candidates"][1]["adjustments"]["color_grading"]["shadows"]["saturation"] > 0


def test_style_reference_upload_rejects_too_many_files_before_analysis() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/references/style-targets",
        files=[("files", (f"ref-{index}.jpg", b"not-an-image", "image/jpeg")) for index in range(13)],
    )

    assert response.status_code == 413
    assert "limited to 12 images" in response.json()["detail"]


def test_lut_reference_endpoints_list_sources_and_profiles() -> None:
    client = TestClient(app)

    sources = client.get("/api/references/luts/sources")
    assert sources.status_code == 200
    assert sources.json()["version"] == 1
    assert any(source["id"] == "user-local-import" for source in sources.json()["sources"])

    profiles = client.get("/api/references/luts/profiles")
    assert profiles.status_code == 200
    assert profiles.json()["root"] == "reference/luts/profiles"
    assert isinstance(profiles.json()["items"], list)

    style_index = client.get("/api/references/luts/style-index")
    assert style_index.status_code == 200
    assert style_index.json()["index"]["kind"] == "lut_style_index"

    preset_sources = client.get("/api/references/presets/sources")
    assert preset_sources.status_code == 200
    assert preset_sources.json()["version"] == 1

    preset_profiles = client.get("/api/references/presets/profiles")
    assert preset_profiles.status_code == 200
    assert preset_profiles.json()["root"] == "reference/presets/profiles"

    preset_style_index = client.get("/api/references/presets/style-index")
    assert preset_style_index.status_code == 200
    assert preset_style_index.json()["index"]["kind"] == "lightroom_preset_style_index"


def test_raw_status_reports_dependency_state() -> None:
    client = TestClient(app)

    response = client.get("/api/raw/status")
    body = response.json()
    assert response.status_code == 200
    assert body["dependency"] == "rawpy"
    assert isinstance(body["available"], bool)
    assert body["install_hint"]


def test_raw_upload_failure_returns_structured_detail() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/images/analyze",
        files={"file": ("broken.dng", b"not a real raw file", "application/octet-stream")},
    )
    body = response.json()
    assert response.status_code == 422
    assert body["detail"]["ok"] is False
    assert body["detail"]["code"] in {"rawpy_missing", "raw_analysis_failed"}
    assert body["detail"]["install_hint"]


def test_image_upload_rejects_files_over_limit(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(settings, "max_upload_bytes", 8)

    response = client.post(
        "/api/images/analyze",
        files={"file": ("too-large.jpg", b"x" * 9, "image/jpeg")},
    )

    assert response.status_code == 413
    assert "exceeds" in response.json()["detail"]


def test_recommend_defaults_to_auto_codex_path(monkeypatch) -> None:
    client = TestClient(app)
    analyze = client.post(
        "/api/images/analyze",
        files={"file": ("smoke.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    analyzed = analyze.json()

    monkeypatch.setattr(recommend_router, "judge_candidates_with_codex", _fake_judge_result)

    response = client.post(
        "/api/recommend",
        json={
            "image_id": analyzed["image_id"],
            "style_prompt": "cool Japanese summer",
            "strength": 0.7,
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ai_status"]["provider"] == "codex-app-server"
    assert body["ai_status"]["status"] == "used"
    assert "AI preview judge" in body["ai_status"]["message"]


def test_recommend_auto_uses_codex_when_available(monkeypatch) -> None:
    client = TestClient(app)
    analyze = client.post(
        "/api/images/analyze",
        files={"file": ("smoke.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    analyzed = analyze.json()

    monkeypatch.setattr(recommend_router, "judge_candidates_with_codex", _fake_judge_result)

    response = client.post(
        "/api/recommend",
        json={
            "image_id": analyzed["image_id"],
            "style_prompt": "cool Japanese summer",
            "strength": 0.7,
            "ai_mode": "auto",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ai_status"]["provider"] == "codex-app-server"
    assert body["ai_status"]["status"] == "used"
    assert [candidate["id"] for candidate in body["candidates"]] == ["natural", "style", "bold"]
    assert body["candidates"][1]["score"] == 0.95


def test_recommend_auto_uses_legacy_codex_when_preview_judge_fails(monkeypatch) -> None:
    client = TestClient(app)
    analyze = client.post(
        "/api/images/analyze",
        files={"file": ("smoke.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    analyzed = analyze.json()

    def fake_judge(**kwargs):
        raise CodexRecommendationError("preview judge offline")

    def fake_codex_recommendations(**kwargs):
        return CodexRecommendationResult(
            candidates=generate_recommendations(kwargs["analysis"], kwargs["style"], kwargs["strength"]),
            message="legacy fake codex candidates",
        )

    monkeypatch.setattr(recommend_router, "judge_candidates_with_codex", fake_judge)
    monkeypatch.setattr(recommend_router, "generate_codex_recommendations", fake_codex_recommendations)

    response = client.post(
        "/api/recommend",
        json={
            "image_id": analyzed["image_id"],
            "style_prompt": "cool Japanese summer",
            "strength": 0.7,
            "ai_mode": "auto",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ai_status"]["status"] == "used"
    assert "legacy Codex recommendation" in body["ai_status"]["message"]


def test_recommend_auto_keeps_style_reference_when_preview_judge_fails(monkeypatch) -> None:
    client = TestClient(app)
    analyze = client.post(
        "/api/images/analyze",
        files={"file": ("smoke.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    analyzed = analyze.json()
    upload = client.post(
        "/api/references/style-targets",
        files=[("files", ("ref.jpg", _reference_jpeg_bytes((32, 54, 112), (220, 174, 104)), "image/jpeg"))],
    )
    reference = upload.json()["reference"]

    def fake_judge(**kwargs):
        raise CodexRecommendationError("preview judge offline")

    def fake_codex_recommendations(**kwargs):
        raise AssertionError("legacy Codex should not replace style-reference candidates")

    monkeypatch.setattr(recommend_router, "judge_candidates_with_codex", fake_judge)
    monkeypatch.setattr(recommend_router, "generate_codex_recommendations", fake_codex_recommendations)

    response = client.post(
        "/api/recommend",
        json={
            "image_id": analyzed["image_id"],
            "style_prompt": "비슷한 느낌으로",
            "strength": 0.7,
            "ai_mode": "auto",
            "style_reference_id": reference["style_reference_id"],
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ai_status"]["status"] == "fallback"
    assert "reference-aware rule fallback" in body["ai_status"]["message"]
    assert "사용자 레퍼런스" in body["candidates"][1]["risk_summary"]


def test_recommend_auto_falls_back_when_codex_fails(monkeypatch) -> None:
    client = TestClient(app)
    analyze = client.post(
        "/api/images/analyze",
        files={"file": ("smoke.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    analyzed = analyze.json()

    def fake_judge(**kwargs):
        raise CodexRecommendationError("preview judge offline")

    def fake_codex_recommendations(**kwargs):
        raise CodexRecommendationError("not logged in")

    monkeypatch.setattr(recommend_router, "judge_candidates_with_codex", fake_judge)
    monkeypatch.setattr(recommend_router, "generate_codex_recommendations", fake_codex_recommendations)

    response = client.post(
        "/api/recommend",
        json={
            "image_id": analyzed["image_id"],
            "style_prompt": "cool Japanese summer",
            "strength": 0.7,
            "ai_mode": "auto",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ai_status"]["provider"] == "codex-app-server"
    assert body["ai_status"]["status"] == "fallback"
    assert [candidate["id"] for candidate in body["candidates"]] == ["natural", "style", "bold"]
