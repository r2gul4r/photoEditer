import type { AnalyzeImageResponse } from "../api/types";

type Props = {
  analysis: AnalyzeImageResponse | null;
};

const labels: Record<string, string> = {
  camera: "카메라",
  lens: "렌즈",
  iso: "ISO",
  shutter: "셔터",
  aperture: "조리개",
  focal_length: "초점거리",
  created_at: "촬영일",
};

export function MetadataPanel({ analysis }: Props) {
  if (!analysis) {
    return <div className="panel-empty">메타데이터</div>;
  }

  const rows = Object.entries(analysis.metadata);

  return (
    <div className="metadata">
      <div className="metric-row">
        <span>{analysis.width} x {analysis.height}</span>
        <span>{analysis.file_type.toUpperCase()}</span>
      </div>
      <table>
        <tbody>
          {rows.map(([key, value]) => (
            <tr key={key}>
              <th>{labels[key] ?? key}</th>
              <td>{value ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

