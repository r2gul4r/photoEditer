from typing import Protocol

import numpy as np


class PromptImageScorer(Protocol):
    """Future local CLIP-like image-text scoring interface."""

    def score(self, image_rgb: np.ndarray, prompt: str) -> float:
        raise NotImplementedError


class AestheticScorer(Protocol):
    """Future local aesthetic scoring interface."""

    def score(self, image_rgb: np.ndarray) -> float:
        raise NotImplementedError


class RegionSegmenter(Protocol):
    """Future sky/skin/green/water segmentation interface."""

    def segment(self, image_rgb: np.ndarray) -> dict[str, np.ndarray]:
        raise NotImplementedError


class OnnxModelRunner(Protocol):
    """Future ONNX Runtime model execution interface."""

    def run(self, model_name: str, inputs: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        raise NotImplementedError

