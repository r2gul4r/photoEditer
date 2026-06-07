from app.models.schemas import CorrectionCandidate
from PIL import Image

from app.services.ai_preview_judge import _prompt, apply_judge_reviews, parse_judge_payload
from app.services.recommendation_engine import generate_recommendations
from app.services.style_interpreter import interpret_style
from app.services.image_analysis import analyze_rgb_array
from app.services.scene_interpreter import interpret_scene
import numpy as np


def _candidates() -> list[CorrectionCandidate]:
    analysis = analyze_rgb_array(np.full((32, 32, 3), 0.5, dtype=np.float32))
    style = interpret_style("cool Japanese summer")
    return generate_recommendations(analysis, style)


def test_parse_judge_payload_returns_reviews_and_best() -> None:
    reviews, best_id, message = parse_judge_payload(
        {
            "s": {
                "n": {"score": 0.72, "reason": "자연스럽지만 스타일 약함", "risk": "낮음"},
                "s": {"score": 0.93, "reason": "청량함과 원본 보존 균형이 좋음", "risk": "없음"},
                "b": {"score": 0.55, "reason": "효과는 강하지만 과함", "risk": "블루 워시"},
            },
            "best": "style",
            "m": "style 후보가 가장 적합함",
        }
    )

    assert best_id == "style"
    assert message == "style 후보가 가장 적합함"
    assert reviews["style"].score == 0.93
    assert reviews["bold"].risk == "블루 워시"


def test_apply_judge_reviews_updates_scores_and_risk_summary() -> None:
    candidates = _candidates()
    reviews, _, _ = parse_judge_payload(
        {
            "s": {
                "n": {"score": 0.7, "reason": "안전함", "risk": "낮음"},
                "s": {"score": 1.0, "reason": "가장 예술적으로 맞음", "risk": "없음"},
                "b": {"score": 0.2, "reason": "너무 파람", "risk": "블루 워시"},
            },
            "best": "style",
            "m": "ok",
        }
    )

    judged = apply_judge_reviews(candidates, reviews)

    assert judged[1].score > candidates[1].score
    assert "AI judge" in (judged[1].risk_summary or "")
    assert any("블루 워시" in warning for warning in judged[2].warnings)


def test_preview_judge_prompt_uses_source_as_preservation_anchor_not_similarity_target() -> None:
    analysis = analyze_rgb_array(np.full((32, 32, 3), 0.5, dtype=np.float32))
    style = interpret_style("cool Japanese summer")
    candidates = generate_recommendations(analysis, style)
    scene = interpret_scene(Image.fromarray(np.full((32, 32, 3), [90, 160, 220], dtype=np.uint8), mode="RGB"))

    prompt = _prompt("cool Japanese summer", style, analysis, candidates, scene)

    assert "preservation anchor" in prompt
    assert "similarity target" in prompt
    assert '"scene"' in prompt
    assert "referenceGroups" in prompt
