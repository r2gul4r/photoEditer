import { Eye, Wand2 } from "lucide-react";

import type { CorrectionCandidate } from "@tonepilot/shared";

type Props = {
  candidate: CorrectionCandidate;
  selected: boolean;
  busy: boolean;
  thumbnailUrl: string | null;
  scoreLabel: string;
  previewLabel: string;
  insightLabels: {
    intent: string;
    tone: string;
    color: string;
    risk: string;
  };
  onPreview: (candidate: CorrectionCandidate) => void;
};

export function CandidateCard({ candidate, selected, busy, thumbnailUrl, scoreLabel, previewLabel, insightLabels, onPreview }: Props) {
  return (
    <article className={`candidate ${selected ? "selected" : ""}`}>
      {thumbnailUrl ? (
        <button className="candidate-thumb" type="button" disabled={busy} onClick={() => onPreview(candidate)}>
          <img src={thumbnailUrl} alt="" aria-hidden="true" />
          <span>{candidate.name}</span>
        </button>
      ) : null}
      <div>
        <div className="candidate-title">
          <Wand2 size={16} aria-hidden="true" />
          <strong>{candidate.name}</strong>
          <span>{Math.round(candidate.score * 100)} {scoreLabel}</span>
        </div>
        <p>{candidate.description}</p>
      </div>
      {candidate.intent || candidate.tone_summary || candidate.color_summary || candidate.risk_summary ? (
        <div className="candidate-insights">
          {candidate.intent ? (
            <div>
              <span>{insightLabels.intent}</span>
              <strong>{candidate.intent}</strong>
            </div>
          ) : null}
          {candidate.tone_summary ? (
            <div>
              <span>{insightLabels.tone}</span>
              <strong>{candidate.tone_summary}</strong>
            </div>
          ) : null}
          {candidate.color_summary ? (
            <div>
              <span>{insightLabels.color}</span>
              <strong>{candidate.color_summary}</strong>
            </div>
          ) : null}
          {candidate.risk_summary ? (
            <div>
              <span>{insightLabels.risk}</span>
              <strong>{candidate.risk_summary}</strong>
            </div>
          ) : null}
        </div>
      ) : null}
      {candidate.warnings.length > 0 ? (
        <ul className="warnings">
          {candidate.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}
      <button className="button ghost" type="button" disabled={busy} onClick={() => onPreview(candidate)}>
        <Eye size={16} aria-hidden="true" />
        {previewLabel}
      </button>
    </article>
  );
}

