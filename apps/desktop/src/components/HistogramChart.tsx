import type { DisplayHistogram, HistogramChannel, ImageAnalysis } from "../api/types";

type Props = {
  analysis: ImageAnalysis | null;
  emptyLabel: string;
};

const VIEWBOX_WIDTH = 256;
const VIEWBOX_HEIGHT = 96;
const TONAL_ZONES = [
  { label: "BLK", x: 0, width: 28 },
  { label: "SHD", x: 28, width: 52 },
  { label: "MID", x: 80, width: 96 },
  { label: "HIL", x: 176, width: 52 },
  { label: "WHT", x: 228, width: 28 },
];

function percent(value: number): string {
  if (value <= 0) return "0.0%";
  if (value < 0.001) return "<0.1%";
  return `${(value * 100).toFixed(1)}%`;
}

function channelAreaPath(channel: HistogramChannel, maxCount: number) {
  const scale = maxCount > 0 ? VIEWBOX_HEIGHT / maxCount : 0;
  const points = channel.bins.map((count, index, bins) => {
    const previous = bins[index - 1] ?? count;
    const next = bins[index + 1] ?? count;
    const smoothed = (previous + count * 2 + next) / 4;
    return {
      x: (index / Math.max(1, bins.length - 1)) * VIEWBOX_WIDTH,
      y: Math.max(0, VIEWBOX_HEIGHT - smoothed * scale),
    };
  });

  if (points.length === 0) return "";

  let path = `M 0 ${VIEWBOX_HEIGHT} L ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`;
  for (let index = 1; index < points.length; index += 1) {
    const previous = points[index - 1];
    const current = points[index];
    const midX = (previous.x + current.x) / 2;
    const midY = (previous.y + current.y) / 2;
    path += ` Q ${previous.x.toFixed(2)} ${previous.y.toFixed(2)} ${midX.toFixed(2)} ${midY.toFixed(2)}`;
  }
  const last = points[points.length - 1];
  path += ` L ${last.x.toFixed(2)} ${last.y.toFixed(2)} L ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT} Z`;
  return path;
}

function channelPeak(channel: HistogramChannel, maxCount: number) {
  if (maxCount <= 0) return 0;
  return Math.round((channel.max_count / maxCount) * 100);
}

function rgbPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function fallbackHistogram(analysis: ImageAnalysis): DisplayHistogram {
  const channels = {
    luma: {
      bins: analysis.luma.histogram_256,
      max_count: Math.max(...analysis.luma.histogram_256),
      clip_black: analysis.luma.histogram_256[0] ?? 0,
      clip_white: analysis.luma.histogram_256[255] ?? 0,
      clip_black_ratio: 0,
      clip_white_ratio: 0,
    },
    r: {
      bins: analysis.rgb.histogram_256.r,
      max_count: Math.max(...analysis.rgb.histogram_256.r),
      clip_black: analysis.rgb.histogram_256.r[0] ?? 0,
      clip_white: analysis.rgb.histogram_256.r[255] ?? 0,
      clip_black_ratio: 0,
      clip_white_ratio: 0,
    },
    g: {
      bins: analysis.rgb.histogram_256.g,
      max_count: Math.max(...analysis.rgb.histogram_256.g),
      clip_black: analysis.rgb.histogram_256.g[0] ?? 0,
      clip_white: analysis.rgb.histogram_256.g[255] ?? 0,
      clip_black_ratio: 0,
      clip_white_ratio: 0,
    },
    b: {
      bins: analysis.rgb.histogram_256.b,
      max_count: Math.max(...analysis.rgb.histogram_256.b),
      clip_black: analysis.rgb.histogram_256.b[0] ?? 0,
      clip_white: analysis.rgb.histogram_256.b[255] ?? 0,
      clip_black_ratio: 0,
      clip_white_ratio: 0,
    },
  };

  const totalPixels = analysis.luma.histogram_256.reduce((sum, count) => sum + count, 0);
  const maxCount = Math.max(channels.luma.max_count, channels.r.max_count, channels.g.max_count, channels.b.max_count);

  return {
    bin_count: 256,
    range_min: 0,
    range_max: 255,
    total_pixels: totalPixels,
    max_count: maxCount,
    shadow_clip: channels.luma.clip_black,
    highlight_clip: channels.luma.clip_white,
    shadow_clip_ratio: totalPixels ? channels.luma.clip_black / totalPixels : 0,
    highlight_clip_ratio: totalPixels ? channels.luma.clip_white / totalPixels : 0,
    channels,
  };
}

export function HistogramChart({ analysis, emptyLabel }: Props) {
  if (!analysis) {
    return <div className="panel-empty">{emptyLabel}</div>;
  }

  const histogram = analysis.display_histogram ?? fallbackHistogram(analysis);
  const maxCount = Math.max(1, histogram.max_count);
  const shadowActive = histogram.shadow_clip > 0;
  const highlightActive = histogram.highlight_clip > 0;
  const lumaPeak = channelPeak(histogram.channels.luma, maxCount);

  return (
    <div className="histogram">
      <div className="histogram-frame">
        <svg
          className="histogram-svg"
          viewBox={`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`}
          preserveAspectRatio="none"
          role="img"
          aria-label="RGB luminance histogram"
        >
          {TONAL_ZONES.map((zone, index) => (
            <rect
              key={zone.label}
              className={`histogram-zone zone-${index}`}
              x={zone.x}
              y="0"
              width={zone.width}
              height={VIEWBOX_HEIGHT}
            />
          ))}
          {[64, 128, 192].map((x) => (
            <line key={x} className="histogram-gridline" x1={x} x2={x} y1="0" y2={VIEWBOX_HEIGHT} />
          ))}
          <path className="histogram-area red" d={channelAreaPath(histogram.channels.r, maxCount)} />
          <path className="histogram-area green" d={channelAreaPath(histogram.channels.g, maxCount)} />
          <path className="histogram-area blue" d={channelAreaPath(histogram.channels.b, maxCount)} />
          <path className="histogram-area luma" d={channelAreaPath(histogram.channels.luma, maxCount)} />
        </svg>
        <span className={shadowActive ? "clip-indicator shadow active" : "clip-indicator shadow"} title="Shadow clipping" />
        <span
          className={highlightActive ? "clip-indicator highlight active" : "clip-indicator highlight"}
          title="Highlight clipping"
        />
        <div className="histogram-tones" aria-hidden="true">
          {TONAL_ZONES.map((zone) => (
            <span key={zone.label}>{zone.label}</span>
          ))}
        </div>
      </div>
      <div className="histogram-scale">
        <span>0</span>
        <span>25</span>
        <span>50</span>
        <span>75</span>
        <span>100</span>
      </div>
      <div className="metric-row histogram-metrics">
        <span>Clip L {percent(histogram.shadow_clip_ratio)}</span>
        <span>Peak {lumaPeak}%</span>
        <span>Clip R {percent(histogram.highlight_clip_ratio)}</span>
      </div>
      <div className="histogram-readout" aria-label="Average RGB values">
        <span>R {rgbPercent(analysis.rgb.r_mean)}</span>
        <span>G {rgbPercent(analysis.rgb.g_mean)}</span>
        <span>B {rgbPercent(analysis.rgb.b_mean)}</span>
      </div>
    </div>
  );
}
