import { useState } from "react";

type Props = {
  originalUrl: string;
  previewUrl: string;
};

export function BeforeAfterView({ originalUrl, previewUrl }: Props) {
  const [split, setSplit] = useState(50);

  return (
    <div className="before-after">
      <img className="before-after-base" src={originalUrl} alt="보정 전" />
      <img
        className="before-after-preview"
        src={previewUrl}
        alt="미리보기"
        style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }}
      />
      <div className="before-after-label before">미리보기</div>
      <div className="before-after-label after">원본</div>
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
