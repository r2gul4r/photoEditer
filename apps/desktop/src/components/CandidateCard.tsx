import { Eye, Wand2 } from "lucide-react";

import type { CorrectionCandidate } from "@tonepilot/shared";

type Props = {
  candidate: CorrectionCandidate;
  selected: boolean;
  busy: boolean;
  scoreLabel: string;
  previewLabel: string;
  onPreview: (candidate: CorrectionCandidate) => void;
};

export function CandidateCard({ candidate, selected, busy, scoreLabel, previewLabel, onPreview }: Props) {
  return (
    <article className={`candidate ${selected ? "selected" : ""}`}>
      <div>
        <div className="candidate-title">
          <Wand2 size={16} aria-hidden="true" />
          <strong>{candidate.name}</strong>
          <span>{Math.round(candidate.score * 100)} {scoreLabel}</span>
        </div>
        <p>{candidate.description}</p>
      </div>
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

