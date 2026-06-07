export type HslAdjustment = {
  hue: number;
  saturation: number;
  luminance: number;
};

export type CropAspect = "original" | "square" | "landscape" | "portrait";

export type ColorGradeAdjustment = {
  hue: number;
  saturation: number;
  luminance: number;
};

export type ColorGradingAdjustment = {
  shadows: ColorGradeAdjustment;
  midtones: ColorGradeAdjustment;
  highlights: ColorGradeAdjustment;
  balance: number;
  blending: number;
};

export type CorrectionAdjustments = {
  exposure: number;
  contrast: number;
  highlights: number;
  shadows: number;
  whites: number;
  blacks: number;
  temperature: number;
  tint: number;
  vibrance: number;
  saturation: number;
  clarity: number;
  texture: number;
  dehaze: number;
  noise_reduction: number;
  vignette_correction: number;
  rotation_degrees: number;
  crop_aspect: CropAspect;
  hsl?: Partial<Record<"red" | "orange" | "yellow" | "green" | "aqua" | "blue" | "purple" | "magenta", HslAdjustment>>;
  color_grading: ColorGradingAdjustment;
};

export type CorrectionCandidate = {
  id: string;
  name: string;
  description: string;
  adjustments: CorrectionAdjustments;
  score: number;
  warnings: string[];
  intent?: string | null;
  tone_summary?: string | null;
  color_summary?: string | null;
  risk_summary?: string | null;
};

