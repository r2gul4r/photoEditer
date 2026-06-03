from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import sys
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def _jpeg_bytes() -> bytes:
    image = Image.new("RGB", (96, 64), (110, 145, 190))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def _post_json(client: TestClient, path: str, body: dict[str, Any]) -> dict[str, Any]:
    response = client.post(path, json=body)
    payload = response.json()
    if response.status_code != 200:
        raise RuntimeError(f"{path} failed with {response.status_code}: {payload}")
    return payload


def run(*, allow_codex_model_call: bool, style_prompt: str, strength: float) -> dict[str, Any]:
    client = TestClient(app)
    status_response = client.get("/api/ai/status")
    status_payload = status_response.json()
    if status_response.status_code != 200:
        raise RuntimeError(f"/api/ai/status failed with {status_response.status_code}: {status_payload}")

    summary: dict[str, Any] = {
        "codex_status": status_payload,
        "model_turn": "skipped",
    }
    if not allow_codex_model_call:
        summary["message"] = (
            "Codex app-server status was checked without starting a model turn. "
            "Pass --allow-codex-model-call to verify real candidate generation."
        )
        return summary

    analyze = client.post(
        "/api/images/analyze",
        files={"file": ("codex-smoke.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    analyzed = analyze.json()
    if analyze.status_code != 200:
        raise RuntimeError(f"analyze failed with {analyze.status_code}: {analyzed}")

    recommendation = _post_json(
        client,
        "/api/recommend",
        {
            "image_id": analyzed["image_id"],
            "style_prompt": style_prompt,
            "strength": strength,
            "ai_mode": "codex",
        },
    )
    candidate_ids = [candidate["id"] for candidate in recommendation["candidates"]]
    if candidate_ids != ["natural", "style", "bold"]:
        raise RuntimeError(f"unexpected candidate ids: {candidate_ids}")
    if recommendation["ai_status"]["provider"] != "codex-app-server":
        raise RuntimeError(f"unexpected provider: {recommendation['ai_status']}")
    if recommendation["ai_status"]["status"] != "used":
        raise RuntimeError(f"Codex was not used: {recommendation['ai_status']}")

    first_candidate = recommendation["candidates"][0]
    preview = _post_json(
        client,
        "/api/preview",
        {
            "image_id": analyzed["image_id"],
            "candidate_id": first_candidate["id"],
            "adjustments": first_candidate["adjustments"],
        },
    )

    summary.update(
        {
            "model_turn": "used",
            "image_id": analyzed["image_id"],
            "candidate_ids": candidate_ids,
            "ai_status": recommendation["ai_status"],
            "preview_url": preview["preview_url"],
        }
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test Codex app-server photo correction.")
    parser.add_argument(
        "--allow-codex-model-call",
        action="store_true",
        help="Run a real Codex recommendation turn. This can consume Codex usage or quota.",
    )
    parser.add_argument("--style-prompt", default="cool Japanese summer")
    parser.add_argument("--strength", type=float, default=0.7)
    args = parser.parse_args()

    summary = run(
        allow_codex_model_call=args.allow_codex_model_call,
        style_prompt=args.style_prompt,
        strength=args.strength,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
