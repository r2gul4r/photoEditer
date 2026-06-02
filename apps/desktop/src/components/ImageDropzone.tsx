import { ImagePlus, Upload } from "lucide-react";
import { useRef, useState } from "react";

type Props = {
  onFile: (file: File) => void;
  busy: boolean;
};

export function ImageDropzone({ onFile, busy }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragging, setDragging] = useState(false);

  function pickFile(file: File | undefined) {
    if (file) onFile(file);
  }

  return (
    <section
      className={`dropzone ${dragging ? "is-dragging" : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        pickFile(event.dataTransfer.files[0]);
      }}
    >
      <input
        id="tonepilot-file-input"
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/tiff,.tif,.tiff,.dng,.arw,.cr2,.cr3,.nef,.orf,.raf,.rw2"
        onChange={(event) => pickFile(event.target.files?.[0])}
      />
      <ImagePlus size={32} aria-hidden="true" />
      <div>
        <strong>사진 열기</strong>
        <span>RAW 우선, JPEG/PNG/TIFF 지원</span>
      </div>
      <button className="button primary" type="button" disabled={busy} onClick={() => inputRef.current?.click()}>
        <Upload size={16} aria-hidden="true" />
        선택
      </button>
    </section>
  );
}
