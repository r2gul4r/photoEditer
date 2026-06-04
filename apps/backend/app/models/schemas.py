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
    intent: str | None = None
    tone_summary: str | None = None
    color_summary: str | None = None
    risk_summary: str | None = None


class StyleInterpretation(BaseModel):
    style_id: str
    mood: list[str]
    targets: list[str]
    avoid: list[str]
    slider_prior: dict[str, tuple[float, float]]
    lut_style_group: str | None = None
    lut_profile_count: int = 0
    lut_match_score: float = 0
    lut_hsl_prior: HslMap = Field(default_factory=dict)
    preset_style_group: str | None = None
    preset_profile_count: int = 0
    preset_match_score: float = 0
    preset_hsl_prior: HslMap = Field(default_factory=dict)


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


LutSourceStatus = Literal["allow", "unknown", "deny"]
LutSourceType = Literal["user_import", "allowed_public_lut"]


class LutSourceEntry(BaseModel):
    id: str
    name: str
    status: LutSourceStatus = "unknown"
    sourceType: LutSourceType = "allowed_public_lut"
    urlPrefixes: list[str] = Field(default_factory=list)
    license: str | None = None
    directDownloadAllowed: bool = False
    notes: str | None = None


class LutSourceRegistry(BaseModel):
    version: int = 1
    sources: list[LutSourceEntry] = Field(default_factory=list)


class LutProfileMetadata(BaseModel):
    sourceUrl: str | None = None
    license: str | None = None
    status: LutSourceStatus
    sourceType: LutSourceType
    downloadedAt: str | None = None
    importedAt: str | None = None
    sha256: str
    originalFilename: str
    originalDeleted: bool


class LutStyleProfile(BaseModel):
    id: str
    version: int = 1
    featureType: Literal["non_invertible_lut_style_profile"] = "non_invertible_lut_style_profile"
    concept: str | None = None
    title: str | None = None
    cubeSize: int
    metadata: LutProfileMetadata
    derivedTags: list[str] = Field(default_factory=list)
    features: dict[str, Any]


class LutIngestResponse(BaseModel):
    profilePath: str
    profile: LutStyleProfile


class LutProfileListResponse(BaseModel):
    root: str = "reference/luts/profiles"
    count: int
    items: list[LutStyleProfile]


class LutUrlIngestRequest(BaseModel):
    sourceUrl: str
    concept: str | None = None


class LutStyleIndexResponse(BaseModel):
    root: str = "reference/luts/style_index.json"
    index: dict[str, Any]


PresetSourceStatus = Literal["allow", "unknown", "deny"]
PresetSourceType = Literal["user_import", "allowed_public_preset"]


class PresetSourceEntry(BaseModel):
    id: str
    name: str
    status: PresetSourceStatus = "unknown"
    sourceType: PresetSourceType = "allowed_public_preset"
    urlPrefixes: list[str] = Field(default_factory=list)
    license: str | None = None
    directDownloadAllowed: bool = False
    notes: str | None = None


class PresetSourceRegistry(BaseModel):
    version: int = 1
    sources: list[PresetSourceEntry] = Field(default_factory=list)


class PresetProfileMetadata(BaseModel):
    sourceUrl: str | None = None
    downloadUrl: str | None = None
    license: str | None = None
    status: PresetSourceStatus
    sourceType: PresetSourceType
    downloadedAt: str | None = None
    importedAt: str | None = None
    sha256: str
    originalFilename: str
    originalDeleted: bool


class PresetStyleProfile(BaseModel):
    id: str
    version: int = 1
    featureType: Literal["lightroom_preset_style_profile"] = "lightroom_preset_style_profile"
    concept: str | None = None
    title: str | None = None
    format: Literal["xmp", "lrtemplate"]
    metadata: PresetProfileMetadata
    derivedTags: list[str] = Field(default_factory=list)
    features: dict[str, Any]


class PresetIngestResponse(BaseModel):
    profilePath: str
    profile: PresetStyleProfile


class PresetProfileListResponse(BaseModel):
    root: str = "reference/presets/profiles"
    count: int
    items: list[PresetStyleProfile]


class PresetStyleIndexResponse(BaseModel):
    root: str = "reference/presets/style_index.json"
    index: dict[str, Any]


class RawSupportStatus(BaseModel):
    available: bool
    dependency: Literal["rawpy"] = "rawpy"
    version: str | None = None
    message: str
    install_hint: str
