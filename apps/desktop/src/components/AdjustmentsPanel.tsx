import type { Language } from "../i18n";
import type { CorrectionAdjustments, HslAdjustment } from "@tonepilot/shared";

type Props = {
  adjustments: CorrectionAdjustments | null;
  language: Language;
  emptyLabel: string;
  group?: AdjustmentGroup;
  busy?: boolean;
  previewLabel?: string;
  onChange?: (adjustments: CorrectionAdjustments) => void;
  onPreview?: () => void;
};

export type AdjustmentGroup = "basic" | "toneCurve" | "color" | "detail" | "masks";
type NumericAdjustmentKey = Exclude<keyof CorrectionAdjustments, "hsl" | "color_grading" | "crop_aspect" | "rotation_degrees">;

const labels: Record<Language, Record<keyof CorrectionAdjustments, string>> = {
  en: {
    exposure: "Exposure",
    contrast: "Contrast",
    highlights: "Highlights",
    shadows: "Shadows",
    whites: "Whites",
    blacks: "Blacks",
    temperature: "Temperature",
    tint: "Tint",
    vibrance: "Vibrance",
    saturation: "Saturation",
    clarity: "Clarity",
    texture: "Texture",
    dehaze: "Dehaze",
    noise_reduction: "Noise Reduction",
    vignette_correction: "Vignette",
    rotation_degrees: "Rotation",
    crop_aspect: "Crop",
    hsl: "HSL",
    color_grading: "Color Grading",
  },
  ko: {
    exposure: "노출",
    contrast: "대비",
    highlights: "하이라이트",
    shadows: "섀도우",
    whites: "화이트",
    blacks: "블랙",
    temperature: "색온도",
    tint: "틴트",
    vibrance: "생동감",
    saturation: "채도",
    clarity: "명료도",
    texture: "텍스처",
    dehaze: "디헤이즈",
    noise_reduction: "노이즈 감소",
    vignette_correction: "비네팅 보정",
    rotation_degrees: "회전",
    crop_aspect: "크롭",
    hsl: "HSL",
    color_grading: "컬러 그레이딩",
  },
};

const numericControls: Array<{
  key: NumericAdjustmentKey;
  min: number;
  max: number;
  step: number;
}> = [
  { key: "exposure", min: -2, max: 2, step: 0.01 },
  { key: "contrast", min: -100, max: 100, step: 1 },
  { key: "highlights", min: -100, max: 100, step: 1 },
  { key: "shadows", min: -100, max: 100, step: 1 },
  { key: "whites", min: -100, max: 100, step: 1 },
  { key: "blacks", min: -100, max: 100, step: 1 },
  { key: "temperature", min: -2000, max: 2000, step: 10 },
  { key: "tint", min: -50, max: 50, step: 1 },
  { key: "vibrance", min: -100, max: 100, step: 1 },
  { key: "saturation", min: -100, max: 100, step: 1 },
  { key: "clarity", min: -100, max: 100, step: 1 },
  { key: "texture", min: -100, max: 100, step: 1 },
  { key: "dehaze", min: -100, max: 100, step: 1 },
  { key: "noise_reduction", min: 0, max: 100, step: 1 },
  { key: "vignette_correction", min: 0, max: 100, step: 1 },
];

const controlsByGroup: Record<AdjustmentGroup, NumericAdjustmentKey[]> = {
  basic: ["exposure", "contrast", "highlights", "shadows", "whites", "blacks"],
  toneCurve: ["contrast", "highlights", "shadows", "whites", "blacks"],
  color: ["temperature", "tint", "vibrance", "saturation"],
  detail: ["clarity", "texture", "dehaze", "noise_reduction", "vignette_correction"],
  masks: ["exposure", "highlights", "shadows", "clarity"],
};

const hslChannels = ["hue", "saturation", "luminance"] as const;
type HslColor = NonNullable<CorrectionAdjustments["hsl"]> extends Partial<Record<infer Color, HslAdjustment>>
  ? Color
  : never;
const hslChannelLabels: Record<Language, Record<(typeof hslChannels)[number], string>> = {
  en: { hue: "H", saturation: "S", luminance: "L" },
  ko: { hue: "H", saturation: "S", luminance: "L" },
};

function formatValue(value: number) {
  return value > 0 ? `+${value}` : `${value}`;
}

export function AdjustmentsPanel({
  adjustments,
  language,
  emptyLabel,
  group = "basic",
  busy = false,
  previewLabel,
  onChange,
  onPreview,
}: Props) {
  if (!adjustments) {
    return <div className="panel-empty">{emptyLabel}</div>;
  }

  const current = adjustments;
  const hslEntries = Object.entries(current.hsl ?? {}) as [HslColor, HslAdjustment][];
  const editable = Boolean(onChange);
  const visibleNumericControls = numericControls.filter(({ key }) => controlsByGroup[group].includes(key));
  const showHsl = group === "color" && hslEntries.length > 0;

  function updateValue(key: NumericAdjustmentKey, value: number) {
    onChange?.({ ...current, [key]: value });
  }

  function updateHslValue(color: HslColor, channel: (typeof hslChannels)[number], value: number) {
    const currentColor = current.hsl?.[color] ?? { hue: 0, saturation: 0, luminance: 0 };
    onChange?.({
      ...current,
      hsl: {
        ...(current.hsl ?? {}),
        [color]: {
          hue: currentColor.hue,
          saturation: currentColor.saturation,
          luminance: currentColor.luminance,
          [channel]: value,
        },
      },
    });
  }

  return (
    <div className="adjustments">
      {visibleNumericControls.map(({ key, min, max, step }) => (
        <label className={`adjustment-row${editable ? " editable" : ""}`} key={key}>
          <span>{labels[language][key]}</span>
          <strong>{formatValue(current[key])}</strong>
          {editable ? (
            <>
              <input
                type="range"
                min={min}
                max={max}
                step={step}
                value={current[key]}
                onChange={(event) => updateValue(key, Number(event.target.value))}
              />
              <input
                className="adjustment-number"
                type="number"
                min={min}
                max={max}
                step={step}
                value={current[key]}
                onChange={(event) => updateValue(key, Number(event.target.value))}
              />
            </>
          ) : null}
        </label>
      ))}
      {showHsl ? (
        <div className="hsl-list">
          <span>HSL</span>
          {hslEntries.map(([color, value]) => (
            <div className="hsl-edit-row" key={color}>
              <small>{color}</small>
              {hslChannels.map((channel) => (
                <label key={channel}>
                  <span>{hslChannelLabels[language][channel]}</span>
                  <input
                    type="number"
                    min={-100}
                    max={100}
                    step={1}
                    value={value[channel]}
                    onChange={(event) => updateHslValue(color, channel, Number(event.target.value))}
                    disabled={!editable}
                  />
                </label>
              ))}
            </div>
          ))}
        </div>
      ) : null}
      {onPreview && previewLabel ? (
        <button className="button ghost full" type="button" disabled={busy} onClick={onPreview}>
          {previewLabel}
        </button>
      ) : null}
    </div>
  );
}

