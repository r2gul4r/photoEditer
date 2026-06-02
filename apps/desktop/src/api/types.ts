export type { CorrectionAdjustments, CorrectionCandidate, HslAdjustment } from "@tonepilot/shared";

export type ImageMetadata = {
  camera: string | null;
  lens: string | null;
  iso: number | null;
  shutter: string | null;
  aperture: string | null;
  focal_length: string | null;
  created_at: string | null;
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
};

export type RecommendResponse = {
  style_interpretation: StyleInterpretation;
  candidates: import("@tonepilot/shared").CorrectionCandidate[];
};

export type PreviewResponse = {
  preview_url: string;
};
