import type { RiskFlags } from "../api/types";
import type { Language } from "../i18n";

type Props = {
  flags: RiskFlags | null;
  language: Language;
  emptyLabel: string;
  safeLabel: string;
};

const labels: Record<Language, Record<keyof RiskFlags, string>> = {
  en: {
    highlight_clipping: "Highlight Clipping",
    shadow_crushing: "Shadow Crushing",
    over_saturated: "Over Saturated",
    too_dark: "Too Dark",
    too_bright: "Too Bright",
    too_flat: "Low Contrast",
    strong_warm_cast: "Warm Cast",
    strong_cool_cast: "Cool Cast",
  },
  ko: {
    highlight_clipping: "하이라이트 클리핑",
    shadow_crushing: "암부 뭉개짐",
    over_saturated: "과채도",
    too_dark: "어두움",
    too_bright: "밝음",
    too_flat: "낮은 대비",
    strong_warm_cast: "웜 캐스트",
    strong_cool_cast: "쿨 캐스트",
  },
};

export function RiskBadges({ flags, language, emptyLabel, safeLabel }: Props) {
  if (!flags) {
    return <div className="risk-list"><span className="risk muted">{emptyLabel}</span></div>;
  }

  const active = Object.entries(flags).filter(([, value]) => value) as [keyof RiskFlags, boolean][];

  if (active.length === 0) {
    return <div className="risk-list"><span className="risk ok">{safeLabel}</span></div>;
  }

  return (
    <div className="risk-list">
      {active.map(([key]) => (
        <span className="risk" key={key}>{labels[language][key]}</span>
      ))}
    </div>
  );
}

