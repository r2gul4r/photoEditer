from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import queue
import subprocess
import threading
import time
from typing import Any

from app.config import settings
from app.models.schemas import (
    AiConnectionStatus,
    CorrectionAdjustments,
    CorrectionCandidate,
    HslAdjustment,
    ImageAnalysis,
    StyleInterpretation,
)
from app.services.recommendation_engine import ADJUSTMENT_LIMITS


class CodexRecommendationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CodexRecommendationResult:
    candidates: list[CorrectionCandidate]
    message: str


HSL_COLORS = ("red", "orange", "yellow", "green", "aqua", "blue", "purple", "magenta")


OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["candidates", "message"],
    "properties": {
        "message": {"type": "string"},
        "candidates": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "name", "description", "adjustments", "score", "warnings"],
                "properties": {
                    "id": {"type": "string", "enum": ["natural", "style", "bold"]},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "score": {"type": "number", "minimum": 0, "maximum": 1},
                    "warnings": {"type": "array", "items": {"type": "string"}},
                    "adjustments": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": list(ADJUSTMENT_LIMITS.keys()) + ["hsl"],
                        "properties": {
                            "exposure": {"type": "number", "minimum": -2, "maximum": 2},
                            "contrast": {"type": "number", "minimum": -100, "maximum": 100},
                            "highlights": {"type": "number", "minimum": -100, "maximum": 100},
                            "shadows": {"type": "number", "minimum": -100, "maximum": 100},
                            "whites": {"type": "number", "minimum": -100, "maximum": 100},
                            "blacks": {"type": "number", "minimum": -100, "maximum": 100},
                            "temperature": {"type": "number", "minimum": -2000, "maximum": 2000},
                            "tint": {"type": "number", "minimum": -50, "maximum": 50},
                            "vibrance": {"type": "number", "minimum": -100, "maximum": 100},
                            "saturation": {"type": "number", "minimum": -100, "maximum": 100},
                            "clarity": {"type": "number", "minimum": -100, "maximum": 100},
                            "texture": {"type": "number", "minimum": -100, "maximum": 100},
                            "dehaze": {"type": "number", "minimum": -100, "maximum": 100},
                            "hsl": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": list(HSL_COLORS),
                                "properties": {
                                    color: {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "required": ["hue", "saturation", "luminance"],
                                        "properties": {
                                            "hue": {"type": "number", "minimum": -100, "maximum": 100},
                                            "saturation": {"type": "number", "minimum": -100, "maximum": 100},
                                            "luminance": {"type": "number", "minimum": -100, "maximum": 100},
                                        },
                                    }
                                    for color in HSL_COLORS
                                },
                            },
                        },
                    },
                },
            },
        },
    },
}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _analysis_payload(analysis: ImageAnalysis) -> dict[str, Any]:
    histogram = analysis.display_histogram
    return {
        "luma": {
            "mean": analysis.luma.mean,
            "std": analysis.luma.std,
            "p01": analysis.luma.p01,
            "p05": analysis.luma.p05,
            "p50": analysis.luma.p50,
            "p95": analysis.luma.p95,
            "p99": analysis.luma.p99,
        },
        "rgb": {
            "r_mean": analysis.rgb.r_mean,
            "g_mean": analysis.rgb.g_mean,
            "b_mean": analysis.rgb.b_mean,
        },
        "saturation": {
            "mean": analysis.saturation.mean,
            "p50": analysis.saturation.p50,
            "p95": analysis.saturation.p95,
        },
        "clipping": {
            "shadow_clip_ratio": histogram.shadow_clip_ratio,
            "highlight_clip_ratio": histogram.highlight_clip_ratio,
            "r_black": histogram.channels["r"].clip_black_ratio,
            "g_black": histogram.channels["g"].clip_black_ratio,
            "b_black": histogram.channels["b"].clip_black_ratio,
            "r_white": histogram.channels["r"].clip_white_ratio,
            "g_white": histogram.channels["g"].clip_white_ratio,
            "b_white": histogram.channels["b"].clip_white_ratio,
        },
        "risk_flags": analysis.risk_flags.model_dump(),
    }


def _prompt(style_prompt: str, style: StyleInterpretation, analysis: ImageAnalysis, strength: float) -> str:
    payload = {
        "style_prompt": style_prompt,
        "strength": strength,
        "style_interpretation": style.model_dump(),
        "analysis": _analysis_payload(analysis),
        "slider_limits": ADJUSTMENT_LIMITS,
    }
    return (
        "You are a local photo-correction advisor for a Lightroom-inspired editor.\n"
        "Return only valid JSON matching the supplied output schema.\n"
        "Generate exactly three candidates: natural, style, bold.\n"
        "Use conservative Lightroom-like slider values. Protect highlights and shadows when clipping risk is present.\n"
        "Do not suggest generative edits, account features, cloud sync, or destructive source-file changes.\n"
        "Candidate names and descriptions must be English.\n\n"
        f"Input data:\n{json.dumps(payload, ensure_ascii=False)}"
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


def _extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise CodexRecommendationError("Codex returned an empty response")
    decoder = json.JSONDecoder()
    try:
        payload, _ = decoder.raw_decode(stripped)
        if isinstance(payload, dict):
            return payload
        raise CodexRecommendationError("Codex JSON was not an object")
    except json.JSONDecodeError:
        start = stripped.find("{")
        if start == -1:
            raise CodexRecommendationError("Codex response did not contain JSON")
        payload, _ = decoder.raw_decode(stripped[start:])
        if not isinstance(payload, dict):
            raise CodexRecommendationError("Codex JSON was not an object")
        return payload


def _clamp_adjustment(name: str, value: Any) -> float:
    low, high = ADJUSTMENT_LIMITS[name]
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.0
    return round(max(low, min(high, numeric)), 2)


def _normalize_candidate(raw: dict[str, Any]) -> CorrectionCandidate:
    candidate_id = raw.get("id")
    if candidate_id not in {"natural", "style", "bold"}:
        raise CodexRecommendationError(f"Invalid candidate id from Codex: {candidate_id!r}")

    raw_adjustments = raw.get("adjustments") if isinstance(raw.get("adjustments"), dict) else {}
    adjustments = {name: _clamp_adjustment(name, raw_adjustments.get(name, 0)) for name in ADJUSTMENT_LIMITS}

    raw_hsl = raw_adjustments.get("hsl", {})
    hsl: dict[str, HslAdjustment] = {}
    if isinstance(raw_hsl, dict):
        for color in HSL_COLORS:
            value = raw_hsl.get(color)
            if not isinstance(value, dict):
                continue
            hsl[color] = HslAdjustment(
                hue=round(float(value.get("hue", 0)), 2),
                saturation=round(float(value.get("saturation", 0)), 2),
                luminance=round(float(value.get("luminance", 0)), 2),
            )

    score = raw.get("score", 0.75)
    try:
        score_value = float(score)
    except (TypeError, ValueError):
        score_value = 0.75

    warnings = raw.get("warnings", [])
    if not isinstance(warnings, list):
        warnings = []

    return CorrectionCandidate(
        id=candidate_id,
        name=str(raw.get("name") or candidate_id.title()),
        description=str(raw.get("description") or "AI-generated correction candidate."),
        adjustments=CorrectionAdjustments(**adjustments, hsl=hsl),
        score=round(max(0.0, min(1.0, score_value)), 2),
        warnings=[str(warning) for warning in warnings],
    )


def _parse_candidates(text: str) -> CodexRecommendationResult:
    payload = _extract_json(text)
    raw_candidates = payload.get("candidates")
    if not isinstance(raw_candidates, list):
        raise CodexRecommendationError("Codex JSON did not include a candidates list")

    candidates = [_normalize_candidate(candidate) for candidate in raw_candidates if isinstance(candidate, dict)]
    by_id = {candidate.id: candidate for candidate in candidates}
    ordered = [by_id.get(candidate_id) for candidate_id in ("natural", "style", "bold")]
    if any(candidate is None for candidate in ordered):
        raise CodexRecommendationError("Codex did not return natural/style/bold candidates")

    return CodexRecommendationResult(
        candidates=[candidate for candidate in ordered if candidate is not None],
        message=str(payload.get("message") or "Codex app-server generated correction candidates."),
    )


class CodexAppServerClient:
    def __init__(self, command: str = "codex", timeout_seconds: float = 90.0) -> None:
        self.command = command
        self.timeout_seconds = timeout_seconds

    def recommend(
        self,
        *,
        style_prompt: str,
        style: StyleInterpretation,
        analysis: ImageAnalysis,
        strength: float,
        image_path: Path | None,
    ) -> CodexRecommendationResult:
        prompt = _prompt(style_prompt, style, analysis, strength)
        root = str(_project_root())
        try:
            proc = subprocess.Popen(
                [self.command, "app-server"],
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
                    "clientInfo": {
                        "name": "photoediter_local",
                        "title": "photoEditer Local",
                        "version": "0.1.0",
                    },
                    "capabilities": {
                        "experimentalApi": True,
                        "optOutNotificationMethods": ["thread/tokenUsage/updated", "turn/plan/updated"],
                    },
                },
                expect_response=True,
            )
            send("initialized", {}, expect_response=False)
            self._wait_for_response(messages, initialize_id)

            thread_id_request = send(
                "thread/start",
                {
                    "cwd": root,
                    "ephemeral": True,
                    "approvalPolicy": "never",
                    "sandbox": "read-only",
                    "baseInstructions": (
                        "You only return photo correction JSON for photoEditer. "
                        "Do not edit files, run shell commands, or discuss implementation."
                    ),
                },
                expect_response=True,
            )
            thread_result = self._wait_for_response(messages, thread_id_request)
            thread_id = thread_result.get("thread", {}).get("id")
            if not thread_id:
                raise CodexRecommendationError("Codex did not return a thread id")

            input_items: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
            if image_path is not None and image_path.exists() and image_path.suffix.lower() not in {".dng", ".arw", ".cr2", ".cr3", ".nef", ".orf", ".raf", ".rw2"}:
                input_items.append({"type": "localImage", "path": str(image_path), "detail": "low"})

            turn_id = send(
                "turn/start",
                {
                    "threadId": thread_id,
                    "cwd": root,
                    "approvalPolicy": "never",
                    "sandbox": "read-only",
                    "input": input_items,
                    "outputSchema": OUTPUT_SCHEMA,
                },
                expect_response=True,
            )
            self._wait_for_response(messages, turn_id)

            final_text = self._collect_turn(messages, thread_id)
            return _parse_candidates(final_text)
        finally:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                proc.kill()

    def probe(self) -> AiConnectionStatus:
        try:
            proc = subprocess.Popen(
                [self.command, "app-server"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except OSError as exc:
            return AiConnectionStatus(
                provider="codex-app-server",
                available=False,
                command=self.command,
                message=f"Could not start Codex app-server: {exc}",
            )
        if proc.stdin is None or proc.stdout is None:
            return AiConnectionStatus(
                provider="codex-app-server",
                available=False,
                command=self.command,
                message="Could not open Codex app-server stdio.",
            )

        messages: queue.Queue[dict[str, Any] | Exception] = queue.Queue()
        reader = threading.Thread(target=_reader, args=(proc.stdout, messages), daemon=True)
        reader.start()

        def send(message: dict[str, Any]) -> None:
            proc.stdin.write(json.dumps(message) + "\n")
            proc.stdin.flush()

        try:
            send(
                {
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "clientInfo": {
                            "name": "photoediter_status",
                            "title": "photoEditer Status",
                            "version": "0.1.0",
                        },
                        "capabilities": {
                            "experimentalApi": True,
                            "optOutNotificationMethods": ["thread/tokenUsage/updated", "turn/plan/updated"],
                        },
                    },
                }
            )
            send({"method": "initialized", "params": {}})
            result = self._wait_for_response(messages, 1)
            return AiConnectionStatus(
                provider="codex-app-server",
                available=True,
                command=self.command,
                message="Codex app-server initialized without starting a model turn.",
                user_agent=str(result.get("userAgent")) if result.get("userAgent") else None,
                platform=str(result.get("platformOs") or result.get("platformFamily") or "") or None,
            )
        except Exception as exc:
            return AiConnectionStatus(
                provider="codex-app-server",
                available=False,
                command=self.command,
                message=str(exc),
            )
        finally:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                proc.kill()

    def _wait_for_response(self, messages: queue.Queue[dict[str, Any] | Exception], request_id: int) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            message = self._next_message(messages, deadline)
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

    def _collect_turn(self, messages: queue.Queue[dict[str, Any] | Exception], thread_id: str) -> str:
        deadline = time.monotonic() + self.timeout_seconds
        chunks: list[str] = []
        completed = False
        while time.monotonic() < deadline:
            message = self._next_message(messages, deadline)
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
            raise CodexRecommendationError("Timed out waiting for Codex turn completion")
        return "".join(chunks)

    @staticmethod
    def _next_message(messages: queue.Queue[dict[str, Any] | Exception], deadline: float) -> dict[str, Any] | Exception:
        timeout = max(0.1, min(1.0, deadline - time.monotonic()))
        try:
            return messages.get(timeout=timeout)
        except queue.Empty:
            return {}


def generate_codex_recommendations(
    *,
    style_prompt: str,
    style: StyleInterpretation,
    analysis: ImageAnalysis,
    strength: float,
    image_path: Path | None,
) -> CodexRecommendationResult:
    client = CodexAppServerClient(command=settings.codex_command, timeout_seconds=settings.codex_timeout_seconds)
    return client.recommend(
        style_prompt=style_prompt,
        style=style,
        analysis=analysis,
        strength=strength,
        image_path=image_path,
    )


def probe_codex_app_server() -> AiConnectionStatus:
    client = CodexAppServerClient(command=settings.codex_command, timeout_seconds=min(settings.codex_timeout_seconds, 10))
    return client.probe()
