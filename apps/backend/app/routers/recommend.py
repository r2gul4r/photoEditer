from fastapi import APIRouter, HTTPException

from app.models.schemas import AiRecommendationStatus, RecommendRequest, RecommendResponse
from app.services.codex_app_server import CodexRecommendationError, generate_codex_recommendations
from app.services.image_store import image_store
from app.services.recommendation_engine import generate_recommendations
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
    if request.ai_mode in {"auto", "codex"}:
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
                    message=codex_result.message,
                ),
            )
        except CodexRecommendationError as exc:
            if request.ai_mode == "codex":
                raise HTTPException(status_code=502, detail=f"Codex app-server recommendation failed: {exc}") from exc
            candidates = generate_recommendations(record.response.analysis, style, request.strength)
            return RecommendResponse(
                style_interpretation=style,
                candidates=candidates,
                ai_status=AiRecommendationStatus(
                    provider="codex-app-server",
                    status="fallback",
                    message=f"Codex app-server unavailable; used rule-based fallback. {exc}",
                ),
            )

    candidates = generate_recommendations(record.response.analysis, style, request.strength)
    return RecommendResponse(
        style_interpretation=style,
        candidates=candidates,
        ai_status=AiRecommendationStatus(
            provider="rules",
            status="not_requested",
            message="Rule-based local recommendation used.",
        ),
    )

