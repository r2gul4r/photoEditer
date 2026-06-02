from typing import Literal

from pydantic import BaseModel, Field


class ImageMetadata(BaseModel):
    camera: str | None = None
    lens: str | None = None
    iso: int | None = None
    shutter: str | None = None
    aperture: str | None = None
    focal_length: str | None = None
    created_at: str | None = None


class LumaStats(BaseModel):
    mean: float
    std: float
    p01: float
    p05: float
    p50: float
    p95: float
    p99: float
    histogram_256: list[int]


class RgbStats(BaseModel):
    r_mean: float
    g_mean: float
    b_mean: float
    histogram_256: dict[Literal["r", "g", "b"], list[int]]


class SaturationStats(BaseModel):
    mean: float
    p50: float
    p95: float
    histogram_256: list[int]


class RiskFlags(BaseModel):
    highlight_clipping: bool
    shadow_crushing: bool
    over_saturated: bool
    too_dark: bool
    too_bright: bool
    too_flat: bool
    strong_warm_cast: bool
    strong_cool_cast: bool


class ImageAnalysis(BaseModel):
    luma: LumaStats
    rgb: RgbStats
    saturation: SaturationStats
    risk_flags: RiskFlags


class AnalyzeImageResponse(BaseModel):
    image_id: str
    filename: str
    file_type: str
    width: int
    height: int
    metadata: ImageMetadata
    analysis: ImageAnalysis


class HslAdjustment(BaseModel):
    hue: float = 0
    saturation: float = 0
    luminance: float = 0


HslMap = dict[
    Literal[
        "red",
        "orange",
        "yellow",
        "green",
        "aqua",
        "blue",
        "purple",
        "magenta",
    ],
    HslAdjustment,
]


class CorrectionAdjustments(BaseModel):
    exposure: float = 0
    contrast: float = 0
    highlights: float = 0
    shadows: float = 0
    whites: float = 0
    blacks: float = 0
    temperature: float = 0
    tint: float = 0
    vibrance: float = 0
    saturation: float = 0
    clarity: float = 0
    texture: float = 0
    dehaze: float = 0
    hsl: HslMap = Field(default_factory=dict)


class CorrectionCandidate(BaseModel):
    id: Literal["natural", "style", "bold"]
    name: str
    description: str
    adjustments: CorrectionAdjustments
    score: float
    warnings: list[str] = Field(default_factory=list)


class StyleInterpretation(BaseModel):
    style_id: str
    mood: list[str]
    targets: list[str]
    avoid: list[str]
    slider_prior: dict[str, tuple[float, float]]


class RecommendRequest(BaseModel):
    image_id: str
    style_prompt: str
    strength: float = Field(default=0.7, ge=0, le=1)


class RecommendResponse(BaseModel):
    style_interpretation: StyleInterpretation
    candidates: list[CorrectionCandidate]


class PreviewRequest(BaseModel):
    image_id: str
    candidate_id: str
    adjustments: CorrectionAdjustments


class PreviewResponse(BaseModel):
    preview_url: str


class ExportPresetRequest(BaseModel):
    image_id: str | None = None
    style_prompt: str | None = None
    candidate: CorrectionCandidate

