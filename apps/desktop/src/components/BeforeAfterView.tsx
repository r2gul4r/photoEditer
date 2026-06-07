import { useState } from "react";
import type { CSSProperties } from "react";

type Props = {
  originalUrl: string;
  previewUrl: string;
  originalLabel: string;
  previewLabel: string;
  imageStyle?: CSSProperties;
};

export function BeforeAfterView({ originalUrl, previewUrl, originalLabel, previewLabel, imageStyle }: Props) {
  const [split, setSplit] = useState(50);

  return (
    <div className="before-after">
      <img className="before-after-base" src={originalUrl} alt={originalLabel} style={imageStyle} />
      <img
        className="before-after-preview"
        src={previewUrl}
        alt={previewLabel}
        style={{ ...imageStyle, clipPath: `inset(0 ${100 - split}% 0 0)` }}
      />
      <span className="before-after-handle" style={{ left: `${split}%` }} aria-hidden="true" />
      <div className="before-after-label before">{originalLabel}</div>
      <div className="before-after-label after">{previewLabel}</div>
      <input
        aria-label="before after slider"
        type="range"
        min={0}
        max={100}
        value={split}
        onChange={(event) => setSplit(Number(event.target.value))}
      />
    </div>
  );
}
