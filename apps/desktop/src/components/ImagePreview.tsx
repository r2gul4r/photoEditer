import { ImageIcon } from "lucide-react";

type Props = {
  imageUrl: string | null;
  filename?: string;
  emptyLabel: string;
  altLabel: string;
};

export function ImagePreview({ imageUrl, filename, emptyLabel, altLabel }: Props) {
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
      <img src={imageUrl} alt={filename ?? altLabel} />
      {filename ? <figcaption>{filename}</figcaption> : null}
    </figure>
  );
}

