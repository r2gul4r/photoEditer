import type { RiskFlags } from "../api/types";

type Props = {
  flags: RiskFlags | null;
};

const labels: Record<keyof RiskFlags, string> = {
  highlight_clipping: "하이라이트 클리핑",
  shadow_crushing: "암부 뭉개짐",
  over_saturated: "과채도",
  too_dark: "어두움",
  too_bright: "밝음",
  too_flat: "낮은 대비",
  strong_warm_cast: "웜 캐스트",
  strong_cool_cast: "쿨 캐스트",
};

export function RiskBadges({ flags }: Props) {
  if (!flags) {
    return <div className="risk-list"><span className="risk muted">위험 요소</span></div>;
  }

  const active = Object.entries(flags).filter(([, value]) => value) as [keyof RiskFlags, boolean][];

  if (active.length === 0) {
    return <div className="risk-list"><span className="risk ok">안전</span></div>;
  }

  return (
    <div className="risk-list">
      {active.map(([key]) => (
        <span className="risk" key={key}>{labels[key]}</span>
      ))}
    </div>
  );
}

