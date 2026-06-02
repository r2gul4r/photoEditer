import io

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app


def _jpeg_bytes() -> bytes:
    image = Image.new("RGB", (96, 64), (110, 145, 190))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


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

    recommend = client.post(
        "/api/recommend",
        json={
            "image_id": analyzed["image_id"],
            "style_prompt": "\uc2dc\uc6d0\ud55c \uc77c\ubcf8 \uc5ec\ub984 \ub290\ub08c",
            "strength": 0.7,
        },
    )
    assert recommend.status_code == 200
    recommendation = recommend.json()
    assert recommendation["style_interpretation"]["style_id"] == "cool_japanese_summer"
    assert [candidate["id"] for candidate in recommendation["candidates"]] == ["natural", "style", "bold"]

    candidate = recommendation["candidates"][0]
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

