from fastapi import APIRouter, HTTPException

from app.models.schemas import RecommendRequest, RecommendResponse
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
    candidates = generate_recommendations(record.response.analysis, style, request.strength)
    return RecommendResponse(style_interpretation=style, candidates=candidates)

