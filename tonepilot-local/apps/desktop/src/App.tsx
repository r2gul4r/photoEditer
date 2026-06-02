import { Download, FolderOpen, Loader2, Settings, Sparkles } from "lucide-react";
import { useRef } from "react";

import { absoluteApiUrl, analyzeImage, downloadPreset, recommend, renderPreview } from "./api/client";
import { AdjustmentsPanel } from "./components/AdjustmentsPanel";
import { BeforeAfterView } from "./components/BeforeAfterView";
import { CandidateCard } from "./components/CandidateCard";
import { HistogramChart } from "./components/HistogramChart";
import { ImageDropzone } from "./components/ImageDropzone";
import { ImagePreview } from "./components/ImagePreview";
import { MetadataPanel } from "./components/MetadataPanel";
import { RiskBadges } from "./components/RiskBadges";
import { useAppStore } from "./state/useAppStore";
import type { CorrectionCandidate } from "@tonepilot/shared";

function App() {
  const [state, dispatch] = useAppStore();
  const topFileInputRef = useRef<HTMLInputElement | null>(null);
  const busy = Boolean(state.busyLabel);
  const imageId = state.analysis?.image_id;

  async function handleFile(file: File) {
    const originalUrl = URL.createObjectURL(file);
    dispatch({ type: "setImage", file, originalUrl });
    try {
      const analysis = await analyzeImage(file);
      dispatch({ type: "setAnalysis", analysis });
    } catch (error) {
      dispatch({ type: "error", error: error instanceof Error ? error.message : "이미지 분석 실패" });
    }
  }

  async function handleRecommend() {
    if (!imageId) return;
    dispatch({ type: "start", label: "추천 생성 중" });
    try {
      const response = await recommend(imageId, state.stylePrompt, state.strength);
      dispatch({ type: "setRecommendation", recommendation: response });
    } catch (error) {
      dispatch({ type: "error", error: error instanceof Error ? error.message : "추천 생성 실패" });
    }
  }

  async function handlePreview(candidate: CorrectionCandidate) {
    if (!imageId) return;
    dispatch({ type: "start", label: "미리보기 렌더링 중" });
    try {
      const response = await renderPreview(imageId, candidate.id, candidate.adjustments);
      dispatch({ type: "setPreview", candidate, previewUrl: absoluteApiUrl(response.preview_url) });
    } catch (error) {
      dispatch({ type: "error", error: error instanceof Error ? error.message : "미리보기 실패" });
    }
  }

  async function handleExport() {
    if (!imageId || !state.selectedCandidate) return;
    dispatch({ type: "start", label: "JSON 내보내기 중" });
    try {
      await downloadPreset(imageId, state.stylePrompt, state.selectedCandidate);
      dispatch({ type: "idle" });
    } catch (error) {
      dispatch({ type: "error", error: error instanceof Error ? error.message : "내보내기 실패" });
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">TP</span>
          <div>
            <strong>TonePilot Local</strong>
            <small>로컬 사진 보정 추천</small>
          </div>
        </div>
        <div className="topbar-actions">
          <input
            ref={topFileInputRef}
            className="hidden-file-input"
            type="file"
            accept="image/jpeg,image/png,image/tiff,.tif,.tiff"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void handleFile(file);
              event.currentTarget.value = "";
            }}
          />
          <button className="button" type="button" onClick={() => topFileInputRef.current?.click()}>
            <FolderOpen size={16} aria-hidden="true" />
            사진 열기
          </button>
          <button className="button" type="button" disabled={!state.selectedCandidate || busy} onClick={handleExport}>
            <Download size={16} aria-hidden="true" />
            JSON 내보내기
          </button>
          <button className="icon-button" type="button" title="설정">
            <Settings size={18} aria-hidden="true" />
          </button>
        </div>
      </header>

      <main className="workspace">
        <section className="preview-pane">
          <div className="preview-toolbar">
            <RiskBadges flags={state.analysis?.analysis.risk_flags ?? null} />
            {state.busyLabel ? (
              <span className="busy">
                <Loader2 size={14} aria-hidden="true" />
                {state.busyLabel}
              </span>
            ) : null}
          </div>
          {state.originalUrl && state.previewUrl ? (
            <BeforeAfterView originalUrl={state.originalUrl} previewUrl={state.previewUrl} />
          ) : (
            <ImagePreview imageUrl={state.originalUrl} filename={state.analysis?.filename} />
          )}
          {!state.originalUrl ? <ImageDropzone onFile={handleFile} busy={busy} /> : null}
          {state.error ? <div className="error-box">{state.error}</div> : null}
        </section>

        <aside className="side-panel">
          <section className="panel">
            <div className="panel-title">
              <span>스타일 키워드</span>
            </div>
            <textarea
              value={state.stylePrompt}
              onChange={(event) => dispatch({ type: "setPrompt", stylePrompt: event.target.value })}
              placeholder="예: 시원한 일본 여름 느낌"
            />
            <label className="strength">
              <span>강도 {Math.round(state.strength * 100)}%</span>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={state.strength}
                onChange={(event) => dispatch({ type: "setStrength", strength: Number(event.target.value) })}
              />
            </label>
            <button className="button primary full" type="button" disabled={!imageId || busy} onClick={handleRecommend}>
              <Sparkles size={16} aria-hidden="true" />
              추천 생성
            </button>
          </section>

          <section className="panel">
            <div className="panel-title">
              <span>추천 후보</span>
              {state.recommendation ? <small>{state.recommendation.style_interpretation.style_id}</small> : null}
            </div>
            <div className="candidate-list">
              {state.recommendation?.candidates.map((candidate) => (
                <CandidateCard
                  key={candidate.id}
                  candidate={candidate}
                  selected={state.selectedCandidate?.id === candidate.id}
                  busy={busy}
                  onPreview={handlePreview}
                />
              )) ?? <div className="panel-empty">Natural / Style / Bold</div>}
            </div>
          </section>

          <section className="panel">
            <div className="panel-title"><span>보정값</span></div>
            <AdjustmentsPanel adjustments={state.selectedCandidate?.adjustments ?? null} />
          </section>

          <section className="panel">
            <div className="panel-title"><span>히스토그램</span></div>
            <HistogramChart analysis={state.analysis?.analysis ?? null} />
          </section>

          <section className="panel">
            <div className="panel-title"><span>메타데이터</span></div>
            <MetadataPanel analysis={state.analysis} />
          </section>
        </aside>
      </main>
    </div>
  );
}

export default App;
