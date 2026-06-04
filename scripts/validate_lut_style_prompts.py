from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path
import sys
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.image_analysis import analyze_image  # noqa: E402
from app.services.recommendation_engine import generate_recommendations  # noqa: E402
from app.services.renderer import render_preview  # noqa: E402
from app.services.style_interpreter import interpret_style  # noqa: E402


PROMPTS: tuple[str, ...] = (
    "\ub530\ub73b\ud55c \uc6e8\ub529 \ub290\ub08c",
    "Lumix real time LUT feel",
    "\ucc28\uac00\uc6b4 \uc601\ud654\ud1a4",
    "cool night city blue",
    "cinematic teal orange",
    "black and white monochrome",
    "warm sunset film",
    "beauty skintone portrait",
    "panasonic rec709 lumix",
)


def create_sample_image() -> Image.Image:
    width, height = 360, 240
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        t = y / max(1, height - 1)
        if y < height * 0.58:
            top = np.array([82, 146, 205])
            bottom = np.array([236, 184, 128])
        else:
            top = np.array([70, 116, 76])
            bottom = np.array([110, 83, 54])
        arr[y, :, :] = (top * (1 - t) + bottom * t).astype(np.uint8)

    image = Image.fromarray(arr, mode="RGB")
    draw = ImageDraw.Draw(image)
    draw.ellipse((262, 28, 330, 96), fill=(248, 205, 116))
    draw.rectangle((0, 142, 360, 240), fill=(74, 112, 76))
    draw.polygon([(0, 240), (88, 142), (170, 240)], fill=(44, 67, 67))
    draw.polygon([(258, 240), (360, 126), (360, 240)], fill=(41, 57, 75))
    draw.ellipse((137, 72, 202, 139), fill=(196, 135, 104))
    draw.rectangle((151, 132, 190, 197), fill=(238, 226, 209))
    draw.polygon([(132, 198), (211, 198), (235, 235), (108, 235)], fill=(226, 218, 207))
    draw.rectangle((32, 76, 106, 132), fill=(62, 103, 146))
    draw.rectangle((246, 118, 330, 175), fill=(161, 91, 67))
    draw.line((0, 166, 360, 150), fill=(235, 205, 148), width=3)
    return image


def mean_abs_delta(left: Image.Image, right: Image.Image) -> float:
    left_arr = np.asarray(left.convert("RGB")).astype(np.float32)
    right_arr = np.asarray(right.convert("RGB").resize(left.size)).astype(np.float32)
    return float(np.mean(np.abs(left_arr - right_arr)))


def image_metrics(image: Image.Image) -> dict[str, Any]:
    arr = np.asarray(image.convert("RGB")).astype(np.float32) / 255.0
    rgb_mean = np.mean(arr, axis=(0, 1))
    luma = arr[..., 0] * 0.2126 + arr[..., 1] * 0.7152 + arr[..., 2] * 0.0722
    maxc = np.max(arr, axis=-1)
    minc = np.min(arr, axis=-1)
    saturation = np.where(maxc <= 1e-6, 0.0, (maxc - minc) / maxc)
    return {
        "rgbMean": [round(float(value), 4) for value in rgb_mean],
        "lumaMean": round(float(np.mean(luma)), 4),
        "saturationMean": round(float(np.mean(saturation)), 4),
    }


def validate(output_root: Path, *, strength: float) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    source = create_sample_image()
    source_path = output_root / "source.jpg"
    source.save(source_path, format="JPEG", quality=92)

    analysis = analyze_image(source)
    source_for_delta = source.resize((320, 213))
    results: list[dict[str, Any]] = []
    rendered: list[tuple[str, Image.Image]] = []

    for index, prompt in enumerate(PROMPTS, start=1):
        style = interpret_style(prompt)
        candidates = generate_recommendations(analysis, style, strength)
        candidate = next(candidate for candidate in candidates if candidate.id == "style")
        preview = render_preview(source, candidate.adjustments, max_side=320)
        filename = f"{index:02d}-{style.lut_style_group or style.style_id}.jpg"
        preview_path = output_root / filename
        preview.save(preview_path, format="JPEG", quality=92)
        rendered.append((prompt, preview))

        adjustments = candidate.adjustments.model_dump()
        results.append(
            {
                "prompt": prompt,
                "styleId": style.style_id,
                "lutStyleGroup": style.lut_style_group,
                "lutProfileCount": style.lut_profile_count,
                "lutMatchScore": round(style.lut_match_score, 2),
                "deltaFromOriginal": round(mean_abs_delta(preview, source_for_delta), 3),
                "metrics": image_metrics(preview),
                "adjustments": {
                    "exposure": adjustments["exposure"],
                    "contrast": adjustments["contrast"],
                    "temperature": adjustments["temperature"],
                    "tint": adjustments["tint"],
                    "vibrance": adjustments["vibrance"],
                    "saturation": adjustments["saturation"],
                    "hsl": adjustments["hsl"],
                },
                "output": str(preview_path.relative_to(ROOT)),
            }
        )

    pairwise_deltas = [
        mean_abs_delta(left_image, right_image)
        for (_, left_image), (_, right_image) in combinations(rendered, 2)
    ]
    unique_groups = sorted({str(result["lutStyleGroup"]) for result in results if result["lutStyleGroup"]})
    summary = {
        "promptCount": len(PROMPTS),
        "uniqueStyleGroupCount": len(unique_groups),
        "uniqueStyleGroups": unique_groups,
        "minPairwiseDelta": round(min(pairwise_deltas), 3),
        "maxPairwiseDelta": round(max(pairwise_deltas), 3),
        "source": str(source_path.relative_to(ROOT)),
        "results": results,
    }

    if summary["uniqueStyleGroupCount"] < 7:
        raise RuntimeError(f"Expected at least 7 LUT style groups, got {unique_groups}")
    if summary["minPairwiseDelta"] < 0.5:
        raise RuntimeError(f"Rendered previews are too similar: min pairwise delta {summary['minPairwiseDelta']}")

    (output_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(output_root / "report.md", summary)
    return summary


def write_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# LUT Style Prompt Validation",
        "",
        f"- prompts: {summary['promptCount']}",
        f"- unique LUT groups: {summary['uniqueStyleGroupCount']} ({', '.join(summary['uniqueStyleGroups'])})",
        f"- min pairwise preview delta: {summary['minPairwiseDelta']}",
        f"- max pairwise preview delta: {summary['maxPairwiseDelta']}",
        f"- source: {summary['source']}",
        "",
        "| prompt | LUT group | profiles | delta | output |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for result in summary["results"]:
        lines.append(
            "| {prompt} | {group} | {count} | {delta} | {output} |".format(
                prompt=str(result["prompt"]).replace("|", "/"),
                group=result["lutStyleGroup"],
                count=result["lutProfileCount"],
                delta=result["deltaFromOriginal"],
                output=result["output"],
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render one sample image through LUT style prompt groups.")
    parser.add_argument("--output", default="test-output/lut-style-validation")
    parser.add_argument("--strength", type=float, default=0.75)
    args = parser.parse_args()

    summary = validate(ROOT / args.output, strength=args.strength)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
