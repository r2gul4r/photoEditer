import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { ImageAnalysis } from "../api/types";

type Props = {
  analysis: ImageAnalysis | null;
};

export function HistogramChart({ analysis }: Props) {
  if (!analysis) {
    return <div className="panel-empty">히스토그램</div>;
  }

  const data = analysis.luma.histogram_256.map((luma, index) => ({
    x: index,
    luma,
    r: analysis.rgb.histogram_256.r[index],
    g: analysis.rgb.histogram_256.g[index],
    b: analysis.rgb.histogram_256.b[index],
  }));

  return (
    <div className="histogram">
      <ResponsiveContainer width="100%" height={164}>
        <LineChart data={data}>
          <XAxis dataKey="x" hide />
          <YAxis hide domain={[0, "dataMax"]} />
          <Tooltip
            contentStyle={{ background: "#171a1f", border: "1px solid #343a43", borderRadius: 6 }}
            labelStyle={{ color: "#e7eaee" }}
          />
          <Line type="monotone" dataKey="luma" stroke="#d8dee9" dot={false} strokeWidth={1.5} />
          <Line type="monotone" dataKey="r" stroke="#f87171" dot={false} strokeWidth={0.8} />
          <Line type="monotone" dataKey="g" stroke="#34d399" dot={false} strokeWidth={0.8} />
          <Line type="monotone" dataKey="b" stroke="#60a5fa" dot={false} strokeWidth={0.8} />
        </LineChart>
      </ResponsiveContainer>
      <div className="metric-row">
        <span>Luma p50 {analysis.luma.p50.toFixed(2)}</span>
        <span>Sat p95 {analysis.saturation.p95.toFixed(2)}</span>
      </div>
    </div>
  );
}

