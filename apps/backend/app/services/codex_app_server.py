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
HSL_CHANNELS = ("hue", "saturation", "luminance")
BASE_SLIDERS = tuple(ADJUSTMENT_LIMITS.keys())
CANDIDATE_KEYS = {"n": "natural", "s": "style", "b": "bold"}
CANDIDATE_LABELS = {
    "natural": ("Natural", "Conservative correction that keeps the original image intact.", 0.88),
    "style": ("Style", "Balanced correction that follows the requested mood.", 0.81),
    "bold": ("Bold", "Stronger correction for a more visible look.", 0.74),
}
COMPACT_VECTOR_LENGTH = len(BASE_SLIDERS) + len(HSL_COLORS) * len(HSL_CHANNELS)


OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["c", "w", "m"],
    "properties": {
        "c": {
            "type": "object",
            "additionalProperties": False,
            "required": list(CANDIDATE_KEYS),
            "properties": {
                key: {
                    "type": "array",
                    "minItems": COMPACT_VECTOR_LENGTH,
                    "maxItems": COMPACT_VECTOR_LENGTH,
                    "items": {"type": "number"},
                }
                for key in CANDIDATE_KEYS
            },
        },
        "w": {
            "type": "object",
            "additionalProperties": False,
            "required": list(CANDIDATE_KEYS),
            "properties": {key: {"type": "array", "items": {"type": "string"}} for key in CANDIDATE_KEYS},
        },
        "m": {"type": "string"},
    },
}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _analysis_payload(analysis: ImageAnalysis) -> dict[str, Any]:
    histogram = analysis.display_histogram
    return {
        "l": [
            analysis.luma.mean,
            analysis.luma.std,
            analysis.luma.p01,
            analysis.luma.p05,
            analysis.luma.p50,
            analysis.luma.p95,
            analysis.luma.p99,
        ],
        "rgb": [analysis.rgb.r_mean, analysis.rgb.g_mean, analysis.rgb.b_mean],
        "sat": [analysis.saturation.mean, analysis.saturation.p50, analysis.saturation.p95],
        "clip": [
            histogram.shadow_clip_ratio,
            histogram.highlight_clip_ratio,
            histogram.channels["r"].clip_black_ratio,
            histogram.channels["g"].clip_black_ratio,
            histogram.channels["b"].clip_black_ratio,
            histogram.channels["r"].clip_white_ratio,
            histogram.channels["g"].clip_white_ratio,
            histogram.channels["b"].clip_white_ratio,
        ],
        "risk": [name for name, enabled in analysis.risk_flags.model_dump().items() if enabled],
    }


def _prompt(style_prompt: str, style: StyleInterpretation, analysis: ImageAnalysis, strength: float) -> str:
    payload = {
        "p": style_prompt,
        "strength": strength,
        "style": {
            "id": style.style_id,
            "mood": style.mood,
            "targets": style.targets,
            "avoid": style.avoid,
            "prior": [style.slider_prior.get(slider, ADJUSTMENT_LIMITS[slider]) for slider in BASE_SLIDERS],
        },
        "a": _analysis_payload(analysis),
    }
    base_order = ",".join(BASE_SLIDERS)
    hsl_order = ",".join(f"{color}_{channel[0]}" for color in HSL_COLORS for channel in HSL_CHANNELS)
    return (
        "Return compact JSON only. Choose Lightroom-like correction values, no generative edits.\n"
        "Output c.n/c.s/c.b as 37-number vectors for natural/style/bold.\n"
        f"Vector order: {base_order},{hsl_order}.\n"
        "Limits: exposure -2..2, temperature -2000..2000, tint -50..50, all other values -100..100.\n"
        "Use n subtle, s balanced, b stronger. Protect clipped highlights/shadows and avoid oversaturation.\n"
        "Return w.n/w.s/w.b as warning string arrays, empty when none; m is a short message.\n"
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


def _clamp_hsl(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.0
    return round(max(-100.0, min(100.0, numeric)), 2)


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
                hue=_clamp_hsl(value.get("hue", 0)),
                saturation=_clamp_hsl(value.get("saturation", 0)),
                luminance=_clamp_hsl(value.get("luminance", 0)),
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


def _candidate_from_vector(candidate_id: str, raw_vector: Any, warnings: list[str]) -> CorrectionCandidate:
    if not isinstance(raw_vector, list) or len(raw_vector) != COMPACT_VECTOR_LENGTH:
        raise CodexRecommendationError(
            f"Codex compact candidate {candidate_id!r} must contain {COMPACT_VECTOR_LENGTH} numbers"
        )

    adjustments = {}
    index = 0
    for name in BASE_SLIDERS:
        adjustments[name] = _clamp_adjustment(name, raw_vector[index])
        index += 1

    hsl: dict[str, HslAdjustment] = {}
    for color in HSL_COLORS:
        values = {}
        for channel in HSL_CHANNELS:
            values[channel] = _clamp_hsl(raw_vector[index])
            index += 1
        hsl[color] = HslAdjustment(
            hue=values["hue"],
            saturation=values["saturation"],
            luminance=values["luminance"],
        )

    name, description, score = CANDIDATE_LABELS[candidate_id]
    return CorrectionCandidate(
        id=candidate_id,  # type: ignore[arg-type]
        name=name,
        description=description,
        adjustments=CorrectionAdjustments(**adjustments, hsl=hsl),
        score=score,
        warnings=warnings,
    )


def _parse_compact_candidates(payload: dict[str, Any]) -> CodexRecommendationResult:
    raw_candidates = payload.get("c")
    if not isinstance(raw_candidates, dict):
        raise CodexRecommendationError("Codex JSON did not include compact candidates")

    raw_warnings = payload.get("w") if isinstance(payload.get("w"), dict) else {}
    candidates: list[CorrectionCandidate] = []
    for compact_key, candidate_id in CANDIDATE_KEYS.items():
        candidate_warnings = raw_warnings.get(compact_key, [])
        if not isinstance(candidate_warnings, list):
            candidate_warnings = []
        candidates.append(
            _candidate_from_vector(
                candidate_id,
                raw_candidates.get(compact_key),
                [str(warning) for warning in candidate_warnings],
            )
        )

    message = payload.get("m") or payload.get("message") or "Codex app-server generated compact correction candidates."
    return CodexRecommendationResult(candidates=candidates, message=str(message))


def _parse_candidates(text: str) -> CodexRecommendationResult:
    payload = _extract_json(text)
    raw_candidates = payload.get("candidates")
    if not isinstance(raw_candidates, list):
        return _parse_compact_candidates(payload)

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
