export type HslAdjustment = {
  hue: number;
  saturation: number;
  luminance: number;
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
  hsl?: Partial<Record<"red" | "orange" | "yellow" | "green" | "aqua" | "blue" | "purple" | "magenta", HslAdjustment>>;
};

export type CorrectionCandidate = {
  id: string;
  name: string;
  description: string;
  adjustments: CorrectionAdjustments;
  score: number;
  warnings: string[];
};

