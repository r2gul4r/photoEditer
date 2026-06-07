import { ImageIcon } from "lucide-react";
import type { CSSProperties } from "react";

type Props = {
  imageUrl: string | null;
  filename?: string;
  emptyLabel: string;
  altLabel: string;
  imageStyle?: CSSProperties;
};

export function ImagePreview({ imageUrl, filename, emptyLabel, altLabel, imageStyle }: Props) {
  if (!imageUrl) {
    return (
      <div className="empty-preview">
        <ImageIcon size={36} aria-hidden="true" />
        <span>{emptyLabel}</span>
      </div>
    );
  }

  return (
    <figure className="image-preview">
      <img src={imageUrl} alt={filename ?? altLabel} style={imageStyle} />
      {filename ? <figcaption>{filename}</figcaption> : null}
    </figure>
  );
}

