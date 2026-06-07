from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import queue
import subprocess
import threading
import time
from typing import Any

from PIL import Image

from app.config import settings
from app.models.schemas import CorrectionAdjustments, CorrectionCandidate, ImageAnalysis, StyleInterpretation
from app.services.codex_app_server import CodexRecommendationError, _extract_json
from app.services.image_store import image_store
from app.services.raw_analysis import render_raw_to_rgb
from app.services.renderer import render_preview
from app.services.scene_interpreter import SceneInterpretation, interpret_scene
from app.utils.image_io import RAW_EXTENSIONS, load_rgb_image


CANDIDATE_KEYS = {"n": "natural", "s": "style", "b": "bold"}

JUDGE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["s", "best", "m"],
    "properties": {
        "s": {
            "type": "object",
            "additionalProperties": False,
            "required": list(CANDIDATE_KEYS),
            "properties": {
                key: {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["score", "reason", "risk"],
                    "properties": {
                        "score": {"type": "number"},
                        "reason": {"type": "string"},
                        "risk": {"type": "string"},
                    },
                }
                for key in CANDIDATE_KEYS
            },
        },
        "best": {"type": "string", "enum": list(CANDIDATE_KEYS.values())},
        "m": {"type": "string"},
    },
}


@dataclass(frozen=True)
class PreviewJudgeReview:
    candidate_id: str
    score: float
    reason: str
    risk: str


@dataclass(frozen=True)
class PreviewJudgeResult:
    candidates: list[CorrectionCandidate]
    message: str
    best_id: str
    reviews: dict[str, PreviewJudgeReview]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _source_image(source_path: Path, file_type: str | None) -> Image.Image:
    if file_type == "raw" or source_path.suffix.lower() in RAW_EXTENSIONS:
        return render_raw_to_rgb(source_path)
    return load_rgb_image(source_path)


def _analysis_payload(analysis: ImageAnalysis) -> dict[str, Any]:
    return {
        "luma": {
            "p50": round(analysis.luma.p50, 4),
            "p95": round(analysis.luma.p95, 4),
            "p99": round(analysis.luma.p99, 4),
            "std": round(analysis.luma.std, 4),
        },
        "rgbMean": [round(analysis.rgb.r_mean, 4), round(analysis.rgb.g_mean, 4), round(analysis.rgb.b_mean, 4)],
        "saturation": {"p50": round(analysis.saturation.p50, 4), "p95": round(analysis.saturation.p95, 4)},
        "risk": [name for name, enabled in analysis.risk_flags.model_dump().items() if enabled],
    }


def _candidate_payload(candidates: list[CorrectionCandidate]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for candidate in candidates:
        adjustments = candidate.adjustments
        payload.append(
            {
                "id": candidate.id,
                "score": candidate.score,
                "tone": candidate.tone_summary,
                "color": candidate.color_summary,
                "risk": candidate.risk_summary,
                "adjustments": {
                    "exposure": adjustments.exposure,
                    "contrast": adjustments.contrast,
                    "highlights": adjustments.highlights,
                    "shadows": adjustments.shadows,
                    "temperature": adjustments.temperature,
                    "vibrance": adjustments.vibrance,
                    "saturation": adjustments.saturation,
                    "clarity": adjustments.clarity,
                    "dehaze": adjustments.dehaze,
                },
            }
        )
    return payload


def _scene_payload(scene: SceneInterpretation) -> dict[str, Any]:
    return {
        "tags": list(scene.scene_tags),
        "protectionPriorities": list(scene.protection_priorities),
        "creativeOpportunities": list(scene.creative_opportunities),
        "regions": {
            name: {
                "coverage": region.coverage,
                "luma": region.luma_mean,
                "saturation": region.saturation_mean,
                "hue": region.hue_mean,
                "role": region.role,
            }
            for name, region in scene.regions.items()
        },
    }


def _prompt(
    style_prompt: str,
    style: StyleInterpretation,
    analysis: ImageAnalysis,
    candidates: list[CorrectionCandidate],
    scene: SceneInterpretation,
) -> str:
    payload = {
        "prompt": style_prompt,
        "style": {
            "id": style.style_id,
            "mood": style.mood,
            "targets": style.targets,
            "avoid": style.avoid,
            "referenceGroups": {
                "preset": style.preset_style_group,
                "lut": style.lut_style_group,
            },
        },
        "analysis": _analysis_payload(analysis),
        "scene": _scene_payload(scene),
        "candidates": _candidate_payload(candidates),
    }
    return (
        "Return compact JSON only. You are an artistic photo preview judge, not an image generator.\n"
        "Images are attached in this exact order: source, natural preview, style preview, bold preview.\n"
        "Use the source image only as a preservation anchor, not as a similarity target.\n"
        "Judge which Lightroom-like preview best matches the prompt, the reference groups, and the interpreted scene roles.\n"
        "Prefer scene-specific color: sky clarity, foliage freshness, neutral whites, protected skin, controlled shadows, and prompt mood.\n"
        "Penalize global blue wash, dead skin tone, clipped highlights, crushed shadows, plastic detail, over-HDR looks, and edits that ignore scene roles.\n"
        "Return Korean reasons. s.n/s.s/s.b each has score 0..1, reason, risk. best is natural/style/bold. m is a short Korean message.\n"
        f"Data:{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}"
    )


def _reader(stdout: Any, messages: queue.Queue[dict[str, Any] | Exception]) -> None:
    try:
        for line in stdout:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                messages.put(json.loads(stripped))
            except json.JSONDecodeError as exc:
                messages.put(exc)
    except Exception as exc:  # pragma: no cover - defensive thread boundary
        messages.put(exc)


def _next_message(messages: queue.Queue[dict[str, Any] | Exception], deadline: float) -> dict[str, Any] | Exception:
    timeout = max(0.1, min(1.0, deadline - time.monotonic()))
    try:
        return messages.get(timeout=timeout)
    except queue.Empty:
        return {}


def _wait_for_response(messages: queue.Queue[dict[str, Any] | Exception], request_id: int, deadline: float) -> dict[str, Any]:
    while time.monotonic() < deadline:
        message = _next_message(messages, deadline)
        if isinstance(message, Exception):
            raise CodexRecommendationError(str(message))
        if message.get("id") != request_id:
            continue
        if "error" in message:
            error = message["error"]
            if isinstance(error, dict):
                raise CodexRecommendationError(str(error.get("message") or error))
            raise CodexRecommendationError(str(error))
        result = message.get("result")
        return result if isinstance(result, dict) else {}
    raise CodexRecommendationError("Timed out waiting for Codex app-server response")


def _collect_turn(messages: queue.Queue[dict[str, Any] | Exception], thread_id: str, deadline: float) -> str:
    chunks: list[str] = []
    completed = False
    while time.monotonic() < deadline:
        message = _next_message(messages, deadline)
        if isinstance(message, Exception):
            raise CodexRecommendationError(str(message))
        method = message.get("method")
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        if params.get("threadId") not in {None, thread_id}:
            continue
        if method == "item/agentMessage/delta":
            chunks.append(str(params.get("delta", "")))
        elif method == "item/completed":
            item = params.get("item", {})
            if isinstance(item, dict) and item.get("type") in {"agent_message", "agentMessage"}:
                text = item.get("text") or item.get("message") or item.get("content")
                if isinstance(text, str) and text and not chunks:
                    chunks.append(text)
        elif method == "turn/completed":
            completed = True
            break
        elif method == "error":
            raise CodexRecommendationError(str(params.get("message") or params))
    if not completed:
        raise CodexRecommendationError("Timed out waiting for Codex preview judge completion")
    return "".join(chunks)


def _run_judge_turn(prompt: str, image_paths: list[Path]) -> dict[str, Any]:
    root = str(_project_root())
    deadline = time.monotonic() + settings.codex_timeout_seconds
    try:
        proc = subprocess.Popen(
            [settings.codex_command, "app-server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
    except OSError as exc:
        raise CodexRecommendationError(f"Could not start Codex app-server: {exc}") from exc
    if proc.stdin is None or proc.stdout is None:
        raise CodexRecommendationError("Could not open Codex app-server stdio")

    messages: queue.Queue[dict[str, Any] | Exception] = queue.Queue()
    reader = threading.Thread(target=_reader, args=(proc.stdout, messages), daemon=True)
    reader.start()
    request_id = 0

    def send(method: str, params: dict[str, Any] | None = None, *, expect_response: bool) -> int:
        nonlocal request_id
        message: dict[str, Any] = {"method": method, "params": params or {}}
        if expect_response:
            message["id"] = request_id
            request_id += 1
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()
        return int(message.get("id", -1))

    try:
        initialize_id = send(
            "initialize",
            {
                "clientInfo": {"name": "photoediter_preview_judge", "title": "photoEditer Preview Judge", "version": "0.1.0"},
                "capabilities": {
                    "experimentalApi": True,
                    "optOutNotificationMethods": ["thread/tokenUsage/updated", "turn/plan/updated"],
                },
            },
            expect_response=True,
        )
        send("initialized", {}, expect_response=False)
        _wait_for_response(messages, initialize_id, deadline)

        thread_id_request = send(
            "thread/start",
            {
                "cwd": root,
                "ephemeral": True,
                "approvalPolicy": "never",
                "sandbox": "read-only",
                "baseInstructions": (
                    "You only judge already-rendered photo correction previews for photoEditer. "
                    "Do not edit files, run commands, or suggest generative image changes."
                ),
            },
            expect_response=True,
        )
        thread_result = _wait_for_response(messages, thread_id_request, deadline)
        thread_id = thread_result.get("thread", {}).get("id")
        if not thread_id:
            raise CodexRecommendationError("Codex did not return a thread id")

        input_items: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        input_items.extend({"type": "localImage", "path": str(path), "detail": "low"} for path in image_paths if path.exists())

        turn_id = send(
            "turn/start",
            {
                "threadId": thread_id,
                "cwd": root,
                "approvalPolicy": "never",
                "sandbox": "read-only",
                "input": input_items,
                "outputSchema": JUDGE_OUTPUT_SCHEMA,
            },
            expect_response=True,
        )
        _wait_for_response(messages, turn_id, deadline)
        return _extract_json(_collect_turn(messages, thread_id, deadline))
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            proc.kill()


def _score(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.0
    return round(max(0.0, min(1.0, numeric)), 2)


def parse_judge_payload(payload: dict[str, Any]) -> tuple[dict[str, PreviewJudgeReview], str, str]:
    raw_scores = payload.get("s")
    if not isinstance(raw_scores, dict):
        raise CodexRecommendationError("Codex preview judge did not return scores")

    reviews: dict[str, PreviewJudgeReview] = {}
    for compact_key, candidate_id in CANDIDATE_KEYS.items():
        raw_review = raw_scores.get(compact_key)
        if not isinstance(raw_review, dict):
            raise CodexRecommendationError(f"Missing preview judge score for {candidate_id}")
        reviews[candidate_id] = PreviewJudgeReview(
            candidate_id=candidate_id,
            score=_score(raw_review.get("score")),
            reason=str(raw_review.get("reason") or ""),
            risk=str(raw_review.get("risk") or ""),
        )

    best_id = str(payload.get("best") or "")
    if best_id not in set(CANDIDATE_KEYS.values()):
        best_id = max(reviews.values(), key=lambda review: review.score).candidate_id
    return reviews, best_id, str(payload.get("m") or "Codex preview judge evaluated rendered previews.")


def apply_judge_reviews(
    candidates: list[CorrectionCandidate],
    reviews: dict[str, PreviewJudgeReview],
) -> list[CorrectionCandidate]:
    judged: list[CorrectionCandidate] = []
    for candidate in candidates:
        review = reviews.get(candidate.id)
        if review is None:
            judged.append(candidate)
            continue
        warnings = list(candidate.warnings)
        normalized_risk = review.risk.strip().casefold()
        if normalized_risk and normalized_risk not in {"none", "no", "없음", "낮음"}:
            warnings.append(f"AI judge: {review.risk}")
        ai_note = f"AI judge {review.score:.2f}: {review.reason}"
        if review.risk:
            ai_note = f"{ai_note} / risk: {review.risk}"
        risk_summary = f"{candidate.risk_summary} / {ai_note}" if candidate.risk_summary else ai_note
        judged.append(
            candidate.model_copy(
                update={
                    "score": round(candidate.score * 0.4 + review.score * 0.6, 2),
                    "warnings": warnings,
                    "risk_summary": risk_summary,
                },
                deep=True,
            )
        )
    return judged


def _render_judge_images(image_id: str, source: Image.Image, candidates: list[CorrectionCandidate]) -> list[Path]:
    source_path = image_store.preview_path(image_id, "ai-judge-source")
    render_preview(source, CorrectionAdjustments(), max_side=720).save(source_path, format="JPEG", quality=88)
    paths = [source_path]
    for candidate in candidates:
        preview_path = image_store.preview_path(image_id, f"ai-judge-{candidate.id}")
        render_preview(source, candidate.adjustments, max_side=720).save(preview_path, format="JPEG", quality=88)
        paths.append(preview_path)
    return paths


def judge_candidates_with_codex(
    *,
    image_id: str,
    style_prompt: str,
    style: StyleInterpretation,
    analysis: ImageAnalysis,
    candidates: list[CorrectionCandidate],
    source_path: Path,
    file_type: str | None,
) -> PreviewJudgeResult:
    try:
        source = _source_image(source_path, file_type)
    except Exception as exc:
        raise CodexRecommendationError(f"Cannot render source image for preview judge: {exc}") from exc

    scene = interpret_scene(source)
    image_paths = _render_judge_images(image_id, source, candidates)
    payload = _run_judge_turn(_prompt(style_prompt, style, analysis, candidates, scene), image_paths)
    reviews, best_id, message = parse_judge_payload(payload)
    return PreviewJudgeResult(
        candidates=apply_judge_reviews(candidates, reviews),
        message=message,
        best_id=best_id,
        reviews=reviews,
    )
