import type { AnalyzeImageResponse } from "../api/types";
import type { Language } from "../i18n";

type Props = {
  analysis: AnalyzeImageResponse | null;
  language: Language;
  emptyLabel: string;
  rawAnalysisLabel: string;
};

const labels: Record<Language, Record<string, string>> = {
  en: {
    camera: "Camera",
    lens: "Lens",
    iso: "ISO",
    shutter: "Shutter",
    aperture: "Aperture",
    focal_length: "Focal Length",
    created_at: "Captured",
  },
  ko: {
    camera: "카메라",
    lens: "렌즈",
    iso: "ISO",
    shutter: "셔터",
    aperture: "조리개",
    focal_length: "초점거리",
    created_at: "촬영일",
  },
};

export function MetadataPanel({ analysis, language, emptyLabel, rawAnalysisLabel }: Props) {
  if (!analysis) {
    return <div className="panel-empty">{emptyLabel}</div>;
  }

  const rows = Object.entries(analysis.metadata);

  return (
    <div className="metadata">
      <div className="metric-row">
        <span>{analysis.width} x {analysis.height}</span>
        <span>
          {analysis.file_type.toUpperCase()}
          {analysis.raw_analysis ? ` / ${rawAnalysisLabel}` : ""}
        </span>
      </div>
      <table>
        <tbody>
          {rows.map(([key, value]) => (
            <tr key={key}>
              <th>{labels[language][key] ?? key}</th>
              <td>{value ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
