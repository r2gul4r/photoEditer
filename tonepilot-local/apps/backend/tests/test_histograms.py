import numpy as np

from app.services.image_analysis import analyze_rgb_array


def test_dark_image_sets_too_dark() -> None:
    image = np.full((32, 32, 3), 0.12, dtype=np.float32)
    analysis = analyze_rgb_array(image)

    assert analysis.risk_flags.too_dark is True
    assert sum(analysis.luma.histogram_256) == 32 * 32


def test_clipped_white_image_sets_highlight_clipping() -> None:
    image = np.ones((32, 32, 3), dtype=np.float32)
    analysis = analyze_rgb_array(image)

    assert analysis.risk_flags.highlight_clipping is True
    assert analysis.risk_flags.too_bright is True


def test_warm_image_sets_warm_cast() -> None:
    image = np.zeros((32, 32, 3), dtype=np.float32)
    image[..., 0] = 0.72
    image[..., 1] = 0.48
    image[..., 2] = 0.32

    analysis = analyze_rgb_array(image)

    assert analysis.risk_flags.strong_warm_cast is True
    assert analysis.rgb.r_mean > analysis.rgb.b_mean

