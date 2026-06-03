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
    allMetadata: "All Metadata",
    metadataSource: "source",
  },
  ko: {
    camera: "카메라",
    lens: "렌즈",
    iso: "ISO",
    shutter: "셔터",
    aperture: "조리개",
    focal_length: "초점거리",
    created_at: "촬영일",
    allMetadata: "전체 메타데이터",
    metadataSource: "소스",
  },
};

const summaryKeys = ["camera", "lens", "iso", "shutter", "aperture", "focal_length", "created_at"] as const;

export function MetadataPanel({ analysis, language, emptyLabel, rawAnalysisLabel }: Props) {
  if (!analysis) {
    return <div className="panel-empty">{emptyLabel}</div>;
  }

  const rows = summaryKeys.map((key) => [key, analysis.metadata[key]] as const);
  const fullRows = analysis.metadata.fields ?? [];

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
      {fullRows.length > 0 ? (
        <details className="metadata-all">
          <summary>
            <span>{labels[language].allMetadata}</span>
            <small>{fullRows.length}</small>
          </summary>
          <div className="metadata-all-table">
            <table>
              <tbody>
                {fullRows.map((field) => (
                  <tr key={`${field.source}-${field.key}`}>
                    <th>
                      {field.key}
                      <small>{labels[language].metadataSource}: {field.source}</small>
                    </th>
                    <td>{field.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      ) : null}
    </div>
  );
}
