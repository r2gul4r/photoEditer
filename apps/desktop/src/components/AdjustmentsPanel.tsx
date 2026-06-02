import type { CorrectionAdjustments } from "@tonepilot/shared";

type Props = {
  adjustments: CorrectionAdjustments | null;
};

const labels: Record<keyof CorrectionAdjustments, string> = {
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
  hsl: "HSL",
};

export function AdjustmentsPanel({ adjustments }: Props) {
  if (!adjustments) {
    return <div className="panel-empty">보정값</div>;
  }

  const entries = Object.entries(adjustments).filter(([key]) => key !== "hsl") as [keyof CorrectionAdjustments, number][];
  const hslEntries = Object.entries(adjustments.hsl ?? {});

  return (
    <div className="adjustments">
      {entries.map(([key, value]) => (
        <div className="adjustment-row" key={key}>
          <span>{labels[key]}</span>
          <strong>{value > 0 ? `+${value}` : value}</strong>
        </div>
      ))}
      {hslEntries.length > 0 ? (
        <div className="hsl-list">
          <span>HSL</span>
          {hslEntries.map(([color, value]) => (
            <small key={color}>
              {color}: H {value.hue > 0 ? `+${value.hue}` : value.hue}, S {value.saturation > 0 ? `+${value.saturation}` : value.saturation}, L {value.luminance > 0 ? `+${value.luminance}` : value.luminance}
            </small>
          ))}
        </div>
      ) : null}
    </div>
  );
}

