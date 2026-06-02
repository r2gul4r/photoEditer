import numpy as np

from app.services.image_analysis import analyze_rgb_array
from app.utils.histograms import histogram_256


def test_dark_image_sets_too_dark() -> None:
    image = np.full((32, 32, 3), 0.12, dtype=np.float32)
    analysis = analyze_rgb_array(image)

    assert analysis.risk_flags.too_dark is True
    assert sum(analysis.luma.histogram_256) == 32 * 32
    assert analysis.display_histogram.bin_count == 256
    assert analysis.display_histogram.range_min == 0
    assert analysis.display_histogram.range_max == 255
    assert analysis.display_histogram.total_pixels == 32 * 32


def test_clipped_white_image_sets_highlight_clipping() -> None:
    image = np.ones((32, 32, 3), dtype=np.float32)
    analysis = analyze_rgb_array(image)

    assert analysis.risk_flags.highlight_clipping is True
    assert analysis.risk_flags.too_bright is True
    assert analysis.display_histogram.highlight_clip == 32 * 32
    assert analysis.display_histogram.channels["r"].clip_white == 32 * 32
    assert analysis.display_histogram.channels["g"].bins[255] == 32 * 32
    assert analysis.display_histogram.channels["b"].bins[255] == 32 * 32


def test_warm_image_sets_warm_cast() -> None:
    image = np.zeros((32, 32, 3), dtype=np.float32)
    image[..., 0] = 0.72
    image[..., 1] = 0.48
    image[..., 2] = 0.32

    analysis = analyze_rgb_array(image)

    assert analysis.risk_flags.strong_warm_cast is True
    assert analysis.rgb.r_mean > analysis.rgb.b_mean


def test_histogram_uses_exact_8_bit_bins() -> None:
    values = np.array([0, 1, 127, 128, 255], dtype=np.uint8)
    histogram = histogram_256(values)

    assert histogram[0] == 1
    assert histogram[1] == 1
    assert histogram[127] == 1
    assert histogram[128] == 1
    assert histogram[255] == 1
    assert sum(histogram) == values.size


def test_display_histogram_tracks_rgb_channel_clipping() -> None:
    image = np.zeros((2, 2, 3), dtype=np.uint8)
    image[0, 0] = [255, 0, 0]
    image[0, 1] = [0, 255, 0]
    image[1, 0] = [0, 0, 255]
    image[1, 1] = [128, 128, 128]

    analysis = analyze_rgb_array(image)
    histogram = analysis.display_histogram

    assert histogram.total_pixels == 4
    assert histogram.shadow_clip == 3
    assert histogram.highlight_clip == 3
    assert histogram.channels["r"].bins[255] == 1
    assert histogram.channels["g"].bins[255] == 1
    assert histogram.channels["b"].bins[255] == 1
    assert histogram.channels["luma"].max_count == 1

