import numpy as np
from PIL import Image, ImageDraw

from app.services.image_analysis import analyze_image
from app.services.recommendation_engine import generate_recommendations
from app.services.renderer import render_preview
from app.services.style_interpreter import interpret_style


def _sample_image() -> Image.Image:
    width, height = 240, 160
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        t = y / max(1, height - 1)
        top = np.array([86, 148, 205])
        bottom = np.array([84, 102, 70])
        arr[y, :, :] = (top * (1 - t) + bottom * t).astype(np.uint8)
    image = Image.fromarray(arr, mode="RGB")
    draw = ImageDraw.Draw(image)
    draw.ellipse((178, 18, 224, 64), fill=(246, 199, 109))
    draw.rectangle((0, 96, width, height), fill=(73, 111, 76))
    draw.ellipse((92, 49, 136, 94), fill=(196, 135, 104))
    draw.rectangle((103, 90, 127, 134), fill=(236, 226, 210))
    draw.rectangle((22, 48, 74, 88), fill=(62, 103, 146))
    draw.rectangle((164, 76, 222, 116), fill=(161, 91, 67))
    return image


def _mean_abs_delta(left: Image.Image, right: Image.Image) -> float:
    left_arr = np.asarray(left.convert("RGB")).astype(np.float32)
    right_arr = np.asarray(right.convert("RGB").resize(left.size)).astype(np.float32)
    return float(np.mean(np.abs(left_arr - right_arr)))


def test_lut_style_prompts_render_distinct_sample_previews() -> None:
    image = _sample_image()
    analysis = analyze_image(image)
    prompt_groups = {
        "\ub530\ub73b\ud55c \uc6e8\ub529 \ub290\ub08c": "wedding_warm",
        "Lumix real time LUT feel": "lumix_realtime",
        "cinematic teal orange": "teal_orange",
        "black and white monochrome": "monochrome",
        "warm sunset film": "warm_sunset",
        "beauty skintone portrait": "beauty_skin",
        "panasonic rec709 lumix": "panasonic_rec709",
    }
    previews: list[Image.Image] = []

    for prompt, expected_group in prompt_groups.items():
        style = interpret_style(prompt)
        assert style.lut_style_group == expected_group

        candidates = generate_recommendations(analysis, style, strength=0.75)
        style_candidate = next(candidate for candidate in candidates if candidate.id == "style")
        preview = render_preview(image, style_candidate.adjustments, max_side=160)
        assert _mean_abs_delta(preview, image) > 0.5
        previews.append(preview)

    deltas = [
        _mean_abs_delta(left, right)
        for index, left in enumerate(previews)
        for right in previews[index + 1 :]
    ]
    assert min(deltas) > 0.5
