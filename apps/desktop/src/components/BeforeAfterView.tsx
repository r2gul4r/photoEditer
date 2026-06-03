import { useState } from "react";

type Props = {
  originalUrl: string;
  previewUrl: string;
  originalLabel: string;
  previewLabel: string;
};

export function BeforeAfterView({ originalUrl, previewUrl, originalLabel, previewLabel }: Props) {
  const [split, setSplit] = useState(50);

  return (
    <div className="before-after">
      <img className="before-after-base" src={originalUrl} alt={originalLabel} />
      <img
        className="before-after-preview"
        src={previewUrl}
        alt={previewLabel}
        style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }}
      />
      <div className="before-after-label before">{previewLabel}</div>
      <div className="before-after-label after">{originalLabel}</div>
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
