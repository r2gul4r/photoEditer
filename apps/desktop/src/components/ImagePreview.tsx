import { ImageIcon } from "lucide-react";

type Props = {
  imageUrl: string | null;
  filename?: string;
};

export function ImagePreview({ imageUrl, filename }: Props) {
  if (!imageUrl) {
    return (
      <div className="empty-preview">
        <ImageIcon size={36} aria-hidden="true" />
        <span>원본</span>
      </div>
    );
  }

  return (
    <figure className="image-preview">
      <img src={imageUrl} alt={filename ?? "원본 사진"} />
      {filename ? <figcaption>{filename}</figcaption> : null}
    </figure>
  );
}

