import numpy as np
from PIL import Image

from app.services.scene_interpreter import interpret_scene


def test_scene_interpreter_detects_editing_roles() -> None:
    arr = np.zeros((100, 140, 3), dtype=np.uint8)
    arr[:44, :, :] = [96, 168, 224]
    arr[44:, :, :] = [76, 132, 70]
    arr[54:82, 22:52, :] = [196, 128, 92]
    arr[50:86, 92:124, :] = [228, 226, 218]
    arr[78:, :24, :] = [24, 28, 28]
    image = Image.fromarray(arr, mode="RGB")

    scene = interpret_scene(image)

    assert scene.has_region("sky", min_coverage=0.08)
    assert scene.has_region("foliage", min_coverage=0.08)
    assert scene.has_region("skin", min_coverage=0.01)
    assert scene.has_region("white_neutral", min_coverage=0.03)
    assert scene.has_region("shadow", min_coverage=0.02)
    assert "sky_present" in scene.scene_tags
    assert "protect neutral whites from color cast" in scene.protection_priorities
    assert any("foliage" in item for item in scene.creative_opportunities)
