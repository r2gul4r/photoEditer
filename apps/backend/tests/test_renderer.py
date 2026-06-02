import numpy as np
from PIL import Image

from app.models.schemas import CorrectionAdjustments
from app.services.renderer import render_preview


def test_renderer_smoke_changes_pixels_and_downscales() -> None:
    source = Image.fromarray(np.full((80, 120, 3), 120, dtype=np.uint8), mode="RGB")
    adjustments = CorrectionAdjustments(
        exposure=0.35,
        contrast=12,
        highlights=-10,
        shadows=8,
        temperature=-300,
        vibrance=18,
        hsl={"blue": {"hue": -3, "saturation": 8, "luminance": 8}},
    )

    preview = render_preview(source, adjustments, max_side=64)

    assert max(preview.size) == 64
    assert preview.mode == "RGB"
    assert np.asarray(preview).mean() != np.asarray(source.resize(preview.size)).mean()

