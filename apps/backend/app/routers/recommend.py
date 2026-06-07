from fastapi import APIRouter, HTTPException

from app.models.schemas import AiRecommendationStatus, RecommendRequest, RecommendResponse
from app.services.ai_preview_judge import judge_candidates_with_codex
from app.services.codex_app_server import CodexRecommendationError, generate_codex_recommendations
from app.services.image_store import image_store
from app.services.recommendation_engine import generate_recommendations
from app.services.style_reference_store import style_reference_store
from app.services.style_interpreter import interpret_style

router = APIRouter(prefix="/api", tags=["recommendations"])


@router.post("/recommend", response_model=RecommendResponse)
def recommend(request: RecommendRequest) -> RecommendResponse:
    try:
        record = image_store.get(request.image_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if record.response is None:
        raise HTTPException(status_code=409, detail="Image has not been analyzed yet")

    style = interpret_style(request.style_prompt)
    style_reference = None
    if request.style_reference_id:
        try:
            style_reference = style_reference_store.get(request.style_reference_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    rule_candidates = generate_recommendations(
        record.response.analysis,
        style,
        request.strength,
        source_path=record.original_path,
        file_type=record.file_type,
        style_reference=style_reference,
    )
    if request.ai_mode in {"auto", "codex"}:
        try:
            judge_result = judge_candidates_with_codex(
                image_id=record.image_id,
                style_prompt=request.style_prompt,
                style=style,
                analysis=record.response.analysis,
                candidates=rule_candidates,
                source_path=record.original_path,
                file_type=record.file_type,
            )
            return RecommendResponse(
                style_interpretation=style,
                candidates=judge_result.candidates,
                ai_status=AiRecommendationStatus(
                    provider="codex-app-server",
                    status="used",
                    message=f"AI preview judge used rendered candidates. Best: {judge_result.best_id}. {judge_result.message}",
                ),
            )
        except CodexRecommendationError as judge_exc:
            if style_reference is None:
                try:
                    codex_result = generate_codex_recommendations(
                        style_prompt=request.style_prompt,
                        style=style,
                        analysis=record.response.analysis,
                        strength=request.strength,
                        image_path=record.original_path,
                    )
                    return RecommendResponse(
                        style_interpretation=style,
                        candidates=codex_result.candidates,
                        ai_status=AiRecommendationStatus(
                            provider="codex-app-server",
                            status="used",
                            message=f"AI preview judge unavailable; used legacy Codex recommendation. {codex_result.message}",
                        ),
                    )
                except CodexRecommendationError as codex_exc:
                    if request.ai_mode == "codex":
                        raise HTTPException(
                            status_code=502,
                            detail=f"Codex app-server preview judge and recommendation failed: {judge_exc}; {codex_exc}",
                        ) from codex_exc
            elif request.ai_mode == "codex":
                raise HTTPException(
                    status_code=502,
                    detail=f"Codex app-server preview judge failed and legacy Codex does not support style_reference_id: {judge_exc}",
                ) from judge_exc
            return RecommendResponse(
                style_interpretation=style,
                candidates=rule_candidates,
                ai_status=AiRecommendationStatus(
                    provider="codex-app-server",
                    status="fallback",
                    message=f"Codex app-server unavailable; used reference-aware rule fallback. {judge_exc}",
                ),
            )

    return RecommendResponse(
        style_interpretation=style,
        candidates=rule_candidates,
        ai_status=AiRecommendationStatus(
            provider="rules",
            status="not_requested",
            message="Rule-based local recommendation used.",
        ),
    )

