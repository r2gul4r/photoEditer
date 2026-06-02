import type { DisplayHistogram, HistogramChannel, ImageAnalysis } from "../api/types";

type Props = {
  analysis: ImageAnalysis | null;
};

const VIEWBOX_WIDTH = 256;
const VIEWBOX_HEIGHT = 96;

function percent(value: number): string {
  if (value <= 0) return "0.0%";
  if (value < 0.001) return "<0.1%";
  return `${(value * 100).toFixed(1)}%`;
}

function channelLines(channel: HistogramChannel, maxCount: number, className: string) {
  const scale = maxCount > 0 ? VIEWBOX_HEIGHT / maxCount : 0;

  return channel.bins.map((count, index) => {
    const y = Math.max(0, VIEWBOX_HEIGHT - count * scale);
    return (
      <line
        key={`${className}-${index}`}
        className={className}
        x1={index + 0.5}
        x2={index + 0.5}
        y1={VIEWBOX_HEIGHT}
        y2={y}
      />
    );
  });
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

export function HistogramChart({ analysis }: Props) {
  if (!analysis) {
    return <div className="panel-empty">히스토그램</div>;
  }

  const histogram = analysis.display_histogram ?? fallbackHistogram(analysis);
  const maxCount = Math.max(1, histogram.max_count);
  const shadowActive = histogram.shadow_clip > 0;
  const highlightActive = histogram.highlight_clip > 0;

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
          <line className="histogram-midline" x1="128" x2="128" y1="0" y2={VIEWBOX_HEIGHT} />
          <g className="histogram-luma">{channelLines(histogram.channels.luma, maxCount, "histogram-line luma")}</g>
          <g>{channelLines(histogram.channels.r, maxCount, "histogram-line red")}</g>
          <g>{channelLines(histogram.channels.g, maxCount, "histogram-line green")}</g>
          <g>{channelLines(histogram.channels.b, maxCount, "histogram-line blue")}</g>
        </svg>
        <span className={shadowActive ? "clip-indicator shadow active" : "clip-indicator shadow"} title="Shadow clipping" />
        <span
          className={highlightActive ? "clip-indicator highlight active" : "clip-indicator highlight"}
          title="Highlight clipping"
        />
      </div>
      <div className="histogram-scale">
        <span>{histogram.range_min}</span>
        <span>128</span>
        <span>{histogram.range_max}</span>
      </div>
      <div className="metric-row histogram-metrics">
        <span>Shadow {percent(histogram.shadow_clip_ratio)}</span>
        <span>Highlight {percent(histogram.highlight_clip_ratio)}</span>
      </div>
    </div>
  );
}
