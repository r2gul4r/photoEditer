import type { DisplayHistogram, HistogramChannel, ImageAnalysis } from "../api/types";

type Props = {
  analysis: ImageAnalysis | null;
  emptyLabel: string;
};

type HistogramSegment = {
  className: string;
  height: number;
  key: string;
  width: number;
  x: number;
  y: number;
};

const VIEWBOX_WIDTH = 256;
const VIEWBOX_HEIGHT = 96;
const CHANNEL_ORDER = ["r", "g", "b"] as const;

function channelHeights(channel: HistogramChannel, maxCount: number) {
  const scale = maxCount > 0 ? VIEWBOX_HEIGHT / maxCount : 0;
  return channel.bins.map((count, index, bins) => {
    const previous = bins[index - 1] ?? count;
    const next = bins[index + 1] ?? count;
    const smoothed = (previous + count * 2 + next) / 4;
    return Math.max(0, Math.min(VIEWBOX_HEIGHT, smoothed * scale));
  });
}

function segmentClass(heights: Record<(typeof CHANNEL_ORDER)[number], number>, upper: number) {
  return CHANNEL_ORDER.filter((channel) => heights[channel] >= upper - 0.001).join("");
}

function histogramSegments(red: number[], green: number[], blue: number[]): HistogramSegment[] {
  const binCount = Math.max(red.length, green.length, blue.length, 1);
  const width = VIEWBOX_WIDTH / binCount;
  const segments: HistogramSegment[] = [];

  for (let index = 0; index < binCount; index += 1) {
    const heights = {
      r: red[index] ?? 0,
      g: green[index] ?? 0,
      b: blue[index] ?? 0,
    };
    const levels = Array.from(new Set([0, heights.r, heights.g, heights.b]))
      .filter((height) => height >= 0)
      .sort((a, b) => a - b);

    for (let levelIndex = 1; levelIndex < levels.length; levelIndex += 1) {
      const lower = levels[levelIndex - 1];
      const upper = levels[levelIndex];
      const height = upper - lower;
      if (height <= 0.15) continue;

      const className = segmentClass(heights, upper);
      if (!className) continue;

      segments.push({
        className,
        height,
        key: `${index}-${className}-${levelIndex}`,
        width: width + 0.08,
        x: index * width,
        y: VIEWBOX_HEIGHT - upper,
      });
    }
  }

  return segments;
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
  const redHeights = channelHeights(histogram.channels.r, maxCount);
  const greenHeights = channelHeights(histogram.channels.g, maxCount);
  const blueHeights = channelHeights(histogram.channels.b, maxCount);
  const segments = histogramSegments(redHeights, greenHeights, blueHeights);

  return (
    <div className="histogram">
      <div className="histogram-frame">
        <svg
          className="histogram-svg"
          viewBox={`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`}
          preserveAspectRatio="none"
          role="img"
          aria-label="RGB histogram"
        >
          {[64, 128, 192].map((x) => (
            <line key={x} className="histogram-gridline" x1={x} x2={x} y1="0" y2={VIEWBOX_HEIGHT} />
          ))}
          {segments.map((segment) => (
            <rect
              key={segment.key}
              className={`histogram-bin ${segment.className}`}
              x={segment.x}
              y={segment.y}
              width={segment.width}
              height={segment.height}
            />
          ))}
        </svg>
        <span className={shadowActive ? "clip-indicator shadow active" : "clip-indicator shadow"} title="Shadow clipping" />
        <span
          className={highlightActive ? "clip-indicator highlight active" : "clip-indicator highlight"}
          title="Highlight clipping"
        />
        <div className="histogram-readout" aria-label="Average RGB values">
          <span>R {rgbPercent(analysis.rgb.r_mean)}</span>
          <span>G {rgbPercent(analysis.rgb.g_mean)}</span>
          <span>B {rgbPercent(analysis.rgb.b_mean)}</span>
        </div>
      </div>
    </div>
  );
}
