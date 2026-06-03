from typing import Any, Literal

from pydantic import BaseModel, Field


class ImageMetadata(BaseModel):
    camera: str | None = None
    lens: str | None = None
    iso: int | None = None
    shutter: str | None = None
    aperture: str | None = None
    focal_length: str | None = None
    created_at: str | None = None
    fields: list["MetadataField"] = Field(default_factory=list)


class MetadataField(BaseModel):
    key: str
    value: str
    source: Literal["pillow", "exifread"]


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


class HistogramChannel(BaseModel):
    bins: list[int]
    max_count: int
    clip_black: int
    clip_white: int
    clip_black_ratio: float
    clip_white_ratio: float


class DisplayHistogram(BaseModel):
    bin_count: int
    range_min: int
    range_max: int
    total_pixels: int
    max_count: int
    shadow_clip: int
    highlight_clip: int
    shadow_clip_ratio: float
    highlight_clip_ratio: float
    channels: dict[Literal["luma", "r", "g", "b"], HistogramChannel]


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
    display_histogram: DisplayHistogram
    risk_flags: RiskFlags


class AnalyzeImageResponse(BaseModel):
    image_id: str
    filename: str
    file_type: str
    width: int
    height: int
    source_preview_url: str | None = None
    metadata: ImageMetadata
    analysis: ImageAnalysis
    raw_analysis: dict[str, Any] | None = None


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


AiMode = Literal["rules", "auto", "codex"]
AiProvider = Literal["rules", "codex-app-server"]
AiStatusValue = Literal["not_requested", "used", "fallback", "failed"]


class AiRecommendationStatus(BaseModel):
    provider: AiProvider
    status: AiStatusValue
    message: str


class AiConnectionStatus(BaseModel):
    provider: Literal["codex-app-server"]
    available: bool
    command: str
    message: str
    user_agent: str | None = None
    platform: str | None = None


class RecommendRequest(BaseModel):
    image_id: str
    style_prompt: str
    strength: float = Field(default=0.7, ge=0, le=1)
    ai_mode: AiMode = "auto"


class RecommendResponse(BaseModel):
    style_interpretation: StyleInterpretation
    candidates: list[CorrectionCandidate]
    ai_status: AiRecommendationStatus


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


class ExportRenderedImageRequest(BaseModel):
    image_id: str
    candidate_id: str
    adjustments: CorrectionAdjustments
    format: Literal["jpeg", "png"] = "jpeg"


class ReferenceSource(BaseModel):
    path: str
    format: str | None = None
    camera: str | None = None
    lens: str | None = None
    iso: int | None = None
    exists: bool = False


class ReferenceTarget(BaseModel):
    path: str
    style: str
    notes: str | None = None
    exists: bool = False


class ReferencePreset(BaseModel):
    path: str
    adjustments: CorrectionAdjustments = Field(default_factory=CorrectionAdjustments)
    exists: bool = False


class ReferenceLicense(BaseModel):
    owner: str | None = None
    usage: str | None = None


class ReferenceManifest(BaseModel):
    id: str
    manifest_path: str
    source: ReferenceSource
    targets: list[ReferenceTarget] = Field(default_factory=list)
    preset: ReferencePreset | None = None
    license: ReferenceLicense | None = None


class ReferenceLibraryResponse(BaseModel):
    root: str = "reference"
    count: int
    items: list[ReferenceManifest]


class RawSupportStatus(BaseModel):
    available: bool
    dependency: Literal["rawpy"] = "rawpy"
    version: str | None = None
    message: str
    install_hint: str
