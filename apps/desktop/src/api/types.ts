export type { CorrectionAdjustments, CorrectionCandidate, HslAdjustment } from "@tonepilot/shared";

export type ImageMetadata = {
  camera: string | null;
  lens: string | null;
  iso: number | null;
  shutter: string | null;
  aperture: string | null;
  focal_length: string | null;
  created_at: string | null;
  fields: MetadataField[];
};

export type MetadataField = {
  key: string;
  value: string;
  source: "pillow" | "exifread";
};

export type LumaStats = {
  mean: number;
  std: number;
  p01: number;
  p05: number;
  p50: number;
  p95: number;
  p99: number;
  histogram_256: number[];
};

export type RgbStats = {
  r_mean: number;
  g_mean: number;
  b_mean: number;
  histogram_256: {
    r: number[];
    g: number[];
    b: number[];
  };
};

export type SaturationStats = {
  mean: number;
  p50: number;
  p95: number;
  histogram_256: number[];
};

export type HistogramChannel = {
  bins: number[];
  max_count: number;
  clip_black: number;
  clip_white: number;
  clip_black_ratio: number;
  clip_white_ratio: number;
};

export type DisplayHistogram = {
  bin_count: number;
  range_min: number;
  range_max: number;
  total_pixels: number;
  max_count: number;
  shadow_clip: number;
  highlight_clip: number;
  shadow_clip_ratio: number;
  highlight_clip_ratio: number;
  channels: {
    luma: HistogramChannel;
    r: HistogramChannel;
    g: HistogramChannel;
    b: HistogramChannel;
  };
};

export type RiskFlags = {
  highlight_clipping: boolean;
  shadow_crushing: boolean;
  over_saturated: boolean;
  too_dark: boolean;
  too_bright: boolean;
  too_flat: boolean;
  strong_warm_cast: boolean;
  strong_cool_cast: boolean;
};

export type AiRecommendationStatus = {
  provider: "rules" | "codex-app-server";
  status: "not_requested" | "used" | "fallback" | "failed";
  message: string;
};

export type AiMode = "auto" | "codex" | "rules";

export type AiConnectionStatus = {
  provider: "codex-app-server";
  available: boolean;
  command: string;
  message: string;
  user_agent: string | null;
  platform: string | null;
};

export type ImageAnalysis = {
  luma: LumaStats;
  rgb: RgbStats;
  saturation: SaturationStats;
  display_histogram: DisplayHistogram;
  risk_flags: RiskFlags;
};

export type AnalyzeImageResponse = {
  image_id: string;
  filename: string;
  file_type: string;
  width: number;
  height: number;
  source_preview_url: string | null;
  metadata: ImageMetadata;
  analysis: ImageAnalysis;
  raw_analysis?: Record<string, unknown> | null;
};

export type StyleInterpretation = {
  style_id: string;
  mood: string[];
  targets: string[];
  avoid: string[];
  slider_prior: Record<string, [number, number]>;
  lut_style_group?: string | null;
  lut_profile_count?: number;
  lut_match_score?: number;
  lut_hsl_prior?: Partial<
    Record<
      "red" | "orange" | "yellow" | "green" | "aqua" | "blue" | "purple" | "magenta",
      import("@tonepilot/shared").HslAdjustment
    >
  >;
  preset_style_group?: string | null;
  preset_profile_count?: number;
  preset_match_score?: number;
  preset_hsl_prior?: Partial<
    Record<
      "red" | "orange" | "yellow" | "green" | "aqua" | "blue" | "purple" | "magenta",
      import("@tonepilot/shared").HslAdjustment
    >
  >;
};

export type RecommendResponse = {
  style_interpretation: StyleInterpretation;
  candidates: import("@tonepilot/shared").CorrectionCandidate[];
  ai_status: AiRecommendationStatus;
};

export type PreviewResponse = {
  preview_url: string;
};

export type ReferenceSource = {
  path: string;
  format: string | null;
  camera: string | null;
  lens: string | null;
  iso: number | null;
  exists: boolean;
};

export type ReferenceTarget = {
  path: string;
  style: string;
  notes: string | null;
  exists: boolean;
};

export type ReferencePreset = {
  path: string;
  adjustments: import("@tonepilot/shared").CorrectionAdjustments;
  exists: boolean;
};

export type ReferenceManifest = {
  id: string;
  manifest_path: string;
  source: ReferenceSource;
  targets: ReferenceTarget[];
  preset: ReferencePreset | null;
  license: {
    owner: string | null;
    usage: string | null;
  } | null;
};

export type ReferenceLibraryResponse = {
  root: "reference";
  count: number;
  items: ReferenceManifest[];
};

export type StyleReferenceSignal = {
  style_reference_id: string;
  count: number;
  filenames: string[];
  summary: string;
  luma_p50: number;
  luma_std: number;
  saturation_mean: number;
  saturation_p50: number;
  warmth_bias: number;
  tint_bias: number;
  shadow_blue_bias: number;
  highlight_warmth_bias: number;
  hsl_prior: Partial<
    Record<
      "red" | "orange" | "yellow" | "green" | "aqua" | "blue" | "purple" | "magenta",
      import("@tonepilot/shared").HslAdjustment
    >
  >;
  color_grading: import("@tonepilot/shared").ColorGradingAdjustment;
};

export type StyleReferenceUploadResponse = {
  reference: StyleReferenceSignal;
};

export type RawSupportStatus = {
  available: boolean;
  dependency: "rawpy";
  version: string | null;
  message: string;
  install_hint: string;
};
