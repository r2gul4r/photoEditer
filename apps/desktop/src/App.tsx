import {
  Aperture,
  BookOpen,
  ChevronRight,
  Columns2,
  Crop,
  Download,
  FileJson,
  Flag,
  FolderOpen,
  Grid2X2,
  Images,
  Languages,
  Loader2,
  Menu,
  Minus,
  RotateCw,
  Settings,
  SlidersHorizontal,
  Sparkles,
  Square,
  Star,
  X,
} from "lucide-react";
import { useEffect, useRef } from "react";

import {
  absoluteApiUrl,
  analyzeImage,
  downloadPreset,
  downloadRenderedImage,
  getAiStatus,
  getRawStatus,
  getReferences,
  recommend,
  renderPreview,
} from "./api/client";
import { AdjustmentsPanel } from "./components/AdjustmentsPanel";
import { BeforeAfterView } from "./components/BeforeAfterView";
import { CandidateCard } from "./components/CandidateCard";
import { HistogramChart } from "./components/HistogramChart";
import { ImageDropzone } from "./components/ImageDropzone";
import { ImagePreview } from "./components/ImagePreview";
import { MetadataPanel } from "./components/MetadataPanel";
import { RiskBadges } from "./components/RiskBadges";
import { copy } from "./i18n";
import { useAppStore } from "./state/useAppStore";
import type { AiMode } from "./api/types";
import type { CorrectionCandidate } from "@tonepilot/shared";

function App() {
  const [state, dispatch] = useAppStore();
  const c = copy[state.language];
  const topFileInputRef = useRef<HTMLInputElement | null>(null);
  const busy = Boolean(state.busyLabel);
  const imageId = state.analysis?.image_id;
  const nextLanguage = state.language === "en" ? "ko" : "en";
  const aiStatus = state.recommendation?.ai_status.status;
  const selectedAiModeLabel =
    state.aiMode === "auto" ? c.aiModeAuto : state.aiMode === "codex" ? c.aiModeCodex : c.aiModeRules;
  const aiStatusLabel =
    aiStatus === "used" ? c.codexUsed : aiStatus === "fallback" ? c.codexFallback : selectedAiModeLabel;
  const aiConnectionLabel = !state.aiConnection
    ? c.codexChecking
    : state.aiConnection.available
      ? c.codexConnected
      : c.codexUnavailable;
  const aiConnectionClass = state.aiConnection?.available ? "available" : state.aiConnection ? "unavailable" : "checking";
  const rawStatusLabel = !state.rawStatus ? c.codexChecking : state.rawStatus.available ? c.rawReady : c.rawUnavailable;
  const loadedFilename = state.analysis?.filename ?? state.imageFile?.name ?? c.noPhoto;
  const referenceItems = state.references?.items ?? [];
  const styleInterpretation = state.recommendation?.style_interpretation;
  const candidateStyleLabel = styleInterpretation
    ? [styleInterpretation.style_id, styleInterpretation.preset_style_group, styleInterpretation.lut_style_group]
        .filter(Boolean)
        .join(" | ")
    : "";

  const moduleItems = [
    { label: c.library, icon: <Images size={19} aria-hidden="true" />, enabled: false },
    { label: c.edit, icon: <SlidersHorizontal size={19} aria-hidden="true" />, active: true, enabled: true },
    { label: c.ai, icon: <Sparkles size={19} aria-hidden="true" />, enabled: false },
    { label: c.reference, icon: <BookOpen size={19} aria-hidden="true" />, enabled: false },
    { label: c.export, icon: <Download size={19} aria-hidden="true" />, enabled: false },
  ];

  const developTabs = [
    { label: c.basic, enabled: true },
    { label: c.toneCurve, enabled: false },
    { label: c.color, enabled: false },
    { label: c.detail, enabled: false },
    { label: c.masks, enabled: false },
  ];
  const aiModeOptions: Array<{ value: AiMode; label: string }> = [
    { value: "auto", label: c.aiModeAuto },
    { value: "codex", label: c.aiModeCodex },
    { value: "rules", label: c.aiModeRules },
  ];
  const megapixels = state.analysis ? ((state.analysis.width * state.analysis.height) / 1_000_000).toFixed(1) : null;
  const captureInfo = [
    state.analysis ? `${state.analysis.width} x ${state.analysis.height}` : null,
    megapixels ? `${megapixels} ${c.megapixels}` : null,
    state.analysis?.file_type.toUpperCase() ?? null,
    state.analysis?.metadata.focal_length,
    state.analysis?.metadata.aperture,
    state.analysis?.metadata.shutter,
    state.analysis?.metadata.iso ? `ISO ${state.analysis.metadata.iso}` : null,
  ].filter(Boolean);
  const insightLabels = { intent: c.intent, tone: c.tone, color: c.color, risk: c.risk };
  const candidateThumbUrl = state.previewUrl ?? state.originalUrl;

  function browserPreviewUrl(file: File): string | null {
    const lowerName = file.name.toLowerCase();
    if (file.type === "image/jpeg" || file.type === "image/png" || lowerName.endsWith(".jpg") || lowerName.endsWith(".jpeg") || lowerName.endsWith(".png")) {
      return URL.createObjectURL(file);
    }
    return null;
  }

  useEffect(() => {
    let cancelled = false;
    void getAiStatus()
      .then((aiConnection) => {
        if (!cancelled) {
          dispatch({ type: "setAiConnection", aiConnection });
        }
      })
      .catch((error) => {
        if (!cancelled) {
          dispatch({
            type: "setAiConnection",
            aiConnection: {
              provider: "codex-app-server",
              available: false,
              command: "codex",
              message: error instanceof Error ? error.message : "Codex status check failed.",
              user_agent: null,
              platform: null,
            },
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    void getReferences()
      .then((references) => {
        if (!cancelled) {
          dispatch({ type: "setReferences", references });
        }
      })
      .catch(() => {
        if (!cancelled) {
          dispatch({ type: "setReferences", references: { root: "reference", count: 0, items: [] } });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    void getRawStatus()
      .then((rawStatus) => {
        if (!cancelled) {
          dispatch({ type: "setRawStatus", rawStatus });
        }
      })
      .catch((error) => {
        if (!cancelled) {
          dispatch({
            type: "setRawStatus",
            rawStatus: {
              available: false,
              dependency: "rawpy",
              version: null,
              message: error instanceof Error ? error.message : "RAW status check failed.",
              install_hint: "Install optional backend dependencies with: pip install -e \"apps/backend[raw]\"",
            },
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleFile(file: File) {
    const originalUrl = browserPreviewUrl(file);
    dispatch({ type: "setImage", file, originalUrl, label: c.analyzeBusy });
    try {
      const analysis = await analyzeImage(file);
      dispatch({
        type: "setAnalysis",
        analysis,
        displayUrl: analysis.source_preview_url ? absoluteApiUrl(analysis.source_preview_url) : undefined,
      });
    } catch (error) {
      dispatch({ type: "error", error: error instanceof Error ? error.message : c.analyzeError });
    }
  }

  async function handleRecommend() {
    if (!imageId) return;
    dispatch({ type: "start", label: c.recommendBusy });
    try {
      const response = await recommend(imageId, state.stylePrompt, state.strength, state.aiMode);
      dispatch({ type: "setRecommendation", recommendation: response });
    } catch (error) {
      dispatch({ type: "error", error: error instanceof Error ? error.message : c.recommendError });
    }
  }

  async function handlePreview(candidate: CorrectionCandidate) {
    if (!imageId) return;
    dispatch({ type: "start", label: c.previewBusy });
    try {
      const response = await renderPreview(imageId, candidate.id, candidate.adjustments);
      dispatch({ type: "setPreview", candidate, previewUrl: absoluteApiUrl(response.preview_url) });
    } catch (error) {
      dispatch({ type: "error", error: error instanceof Error ? error.message : c.previewError });
    }
  }

  async function handlePresetExport() {
    if (!imageId || !state.selectedCandidate) return;
    dispatch({ type: "start", label: c.jsonBusy });
    try {
      await downloadPreset(imageId, state.stylePrompt, state.selectedCandidate);
      dispatch({ type: "idle" });
    } catch (error) {
      dispatch({ type: "error", error: error instanceof Error ? error.message : c.jsonError });
    }
  }

  async function handleImageExport() {
    if (!imageId || !state.selectedCandidate) return;
    dispatch({ type: "start", label: c.imageBusy });
    try {
      await downloadRenderedImage(imageId, state.selectedCandidate, "jpeg");
      dispatch({ type: "idle" });
    } catch (error) {
      dispatch({ type: "error", error: error instanceof Error ? error.message : c.imageError });
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">TP</span>
          <div>
            <strong>TonePilot Local</strong>
            <small>{c.appSubtitle}</small>
          </div>
        </div>
        <div className="topbar-path" aria-label="Current photo">
          <span>{state.analysis?.metadata.created_at ?? c.localOnly}</span>
          <ChevronRight size={14} aria-hidden="true" />
          <strong>{loadedFilename}</strong>
        </div>
        <div className="topbar-actions">
          <input
            ref={topFileInputRef}
            className="hidden-file-input"
            type="file"
            accept="image/jpeg,image/png,image/tiff,.tif,.tiff,.dng,.arw,.cr2,.cr3,.nef,.orf,.raf,.rw2"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void handleFile(file);
              event.currentTarget.value = "";
            }}
          />
          <button className="button" type="button" onClick={() => topFileInputRef.current?.click()}>
            <FolderOpen size={16} aria-hidden="true" />
            {c.openPhoto}
          </button>
          <button className="button" type="button" disabled={!state.selectedCandidate || busy} onClick={handleImageExport}>
            <Download size={16} aria-hidden="true" />
            {c.exportImage}
          </button>
          <button className="button" type="button" disabled={!state.selectedCandidate || busy} onClick={handlePresetExport}>
            <FileJson size={16} aria-hidden="true" />
            {c.exportJson}
          </button>
          <button
            className="icon-text-button"
            type="button"
            title={c.language}
            onClick={() => dispatch({ type: "setLanguage", language: nextLanguage })}
          >
            <Languages size={17} aria-hidden="true" />
            {state.language.toUpperCase()}
          </button>
          <button className="icon-button" type="button" title={c.plannedFeature} disabled>
            <Settings size={18} aria-hidden="true" />
          </button>
          <span className="topbar-divider" aria-hidden="true" />
          <button className="icon-button quiet" type="button" title={c.plannedFeature} disabled>
            <Menu size={18} aria-hidden="true" />
          </button>
          <button className="icon-button quiet window-control" type="button" title={c.plannedFeature} disabled>
            <Minus size={16} aria-hidden="true" />
          </button>
          <button className="icon-button quiet window-control" type="button" title={c.plannedFeature} disabled>
            <Square size={14} aria-hidden="true" />
          </button>
          <button className="icon-button quiet window-control" type="button" title={c.plannedFeature} disabled>
            <X size={16} aria-hidden="true" />
          </button>
        </div>
      </header>

      <main className="workspace editor-workspace">
        <nav className="module-rail" aria-label="Editor modules">
          {moduleItems.map((item) => (
            <button
              key={item.label}
              className={`module-button${item.active ? " active" : ""}`}
              type="button"
              disabled={!item.enabled}
              title={item.enabled ? item.label : c.plannedFeature}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <section className="canvas-pane">
          <div className="editor-toolbar">
            <div className="toolbar-group">
              <button className="tool-chip" type="button" disabled title={c.plannedFeature}>
                <Crop size={15} aria-hidden="true" />
                {c.crop}
              </button>
              <button className="tool-chip" type="button" disabled title={c.plannedFeature}>
                <RotateCw size={15} aria-hidden="true" />
                {c.rotate}
              </button>
              <button className="tool-chip" type="button" disabled title={state.previewUrl ? c.sourceFirst : c.plannedFeature}>
                <Columns2 size={15} aria-hidden="true" />
                {c.compare}
              </button>
            </div>
            <div className="toolbar-group status-tools">
              <RiskBadges
                flags={state.analysis?.analysis.risk_flags ?? null}
                language={state.language}
                emptyLabel={c.risks}
                safeLabel={c.safe}
              />
              {state.busyLabel ? (
                <span className="busy">
                  <Loader2 size={14} aria-hidden="true" />
                  {state.busyLabel}
                </span>
              ) : null}
            </div>
          </div>

          <div className="photo-stage">
            {!state.originalUrl ? (
              <div className="empty-preview stage-empty-bg">
                {busy ? <Loader2 size={28} aria-hidden="true" /> : null}
                {busy ? <span>{state.busyLabel ?? c.noPhoto}</span> : null}
              </div>
            ) : state.previewUrl ? (
              <BeforeAfterView
                originalUrl={state.originalUrl}
                previewUrl={state.previewUrl}
                originalLabel={c.original}
                previewLabel={c.preview}
              />
            ) : (
              <ImagePreview
                imageUrl={state.originalUrl}
                filename={loadedFilename}
                emptyLabel={c.noPhoto}
                altLabel={c.originalPhoto}
              />
            )}
            {!state.originalUrl && !busy ? (
              <div className="stage-dropzone">
                <ImageDropzone
                  onFile={handleFile}
                  busy={busy}
                  title={c.dropTitle}
                  subtitle={c.dropSubtitle}
                  selectLabel={c.select}
                />
              </div>
            ) : null}
          </div>

          <div className="photo-info-row">
            <div className="view-tools" aria-label="View tools">
              <button className="mini-tool" type="button" disabled title={c.plannedFeature}>
                <Grid2X2 size={15} aria-hidden="true" />
              </button>
              <button className="mini-tool" type="button" disabled title={c.plannedFeature}>
                <Columns2 size={15} aria-hidden="true" />
              </button>
              <span className="zoom-chip">Fit</span>
              <span className="zoom-chip">100%</span>
            </div>
            <div className="rating-strip" aria-label="Rating">
              {[0, 1, 2, 3, 4].map((value) => (
                <Star key={value} size={14} aria-hidden="true" />
              ))}
              <Flag size={14} aria-hidden="true" />
            </div>
            <div className="capture-info">
              {captureInfo.length ? captureInfo.map((item) => <span key={item}>{item}</span>) : <span>{c.noPhoto}</span>}
            </div>
          </div>

          {state.error ? <div className="error-box">{state.error}</div> : null}

          <div className="filmstrip">
            <div className="strip-header">
              <span>{c.filmstrip}</span>
              <small>{c.references}: {state.references?.count ?? 0}</small>
            </div>
            <div className="strip-list">
              <button className={`strip-thumb${state.originalUrl ? " active" : ""}`} type="button" disabled={!state.originalUrl}>
                {state.originalUrl ? <img src={state.originalUrl} alt={loadedFilename} /> : <span className="thumb-placeholder" />}
                <span>{c.original}</span>
              </button>
              <button className={`strip-thumb${state.previewUrl ? " active" : ""}`} type="button" disabled={!state.previewUrl}>
                {state.previewUrl ? <img src={state.previewUrl} alt={c.preview} /> : <span className="thumb-placeholder" />}
                <span>{c.preview}</span>
              </button>
              <div className="extension-slot compact">
                <strong>{c.references}</strong>
                <span>{state.references?.count ?? 0} manifest</span>
              </div>
            </div>
          </div>
        </section>

        <aside className="inspector-panel">
          <section className="inspector-block histogram-block">
            <div className="inspector-title">
              <span>{c.histogram}</span>
              <small>{c.sourceFirst}</small>
            </div>
            <HistogramChart analysis={state.analysis?.analysis ?? null} emptyLabel={c.histogram} />
          </section>

          <section className="inspector-block">
            <div className="inspector-title">
              <span>{c.aiCorrection}</span>
              <small className={`ai-status ${aiStatus ?? "idle"}`}>{aiStatusLabel}</small>
            </div>
            <div className="control-stack">
              <textarea
                value={state.stylePrompt}
                onChange={(event) => dispatch({ type: "setPrompt", stylePrompt: event.target.value })}
                placeholder={c.stylePlaceholder}
              />
              <div className="mode-toggle" aria-label={c.aiMode}>
                <span>{c.aiMode}</span>
                <div>
                  {aiModeOptions.map((option) => (
                    <button
                      key={option.value}
                      className={`mode-button${state.aiMode === option.value ? " active" : ""}`}
                      type="button"
                      onClick={() => dispatch({ type: "setAiMode", aiMode: option.value })}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className={`connection-line ${aiConnectionClass}`} title={state.aiConnection?.message ?? c.codexChecking}>
                <span>{c.aiConnection}</span>
                <strong>{aiConnectionLabel}</strong>
              </div>
              <label className="control-row">
                <span>{c.strength}</span>
                <strong>{Math.round(state.strength * 100)}%</strong>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.01}
                  value={state.strength}
                  onChange={(event) =>
                    dispatch({ type: "setStrength", strength: Math.round(Number(event.target.value) * 100) / 100 })
                  }
                />
              </label>
              <button className="button primary full" type="button" disabled={!imageId || busy} onClick={handleRecommend}>
                <Sparkles size={16} aria-hidden="true" />
                {c.generate}
              </button>
            </div>
          </section>

          <section className="inspector-block">
            <div className="inspector-title">
              <span>{c.candidates}</span>
              {state.recommendation ? <small>{candidateStyleLabel}</small> : null}
            </div>
            <div className="candidate-list">
              {state.recommendation?.candidates.length ? (
                state.recommendation.candidates.map((candidate) => (
                  <CandidateCard
                    key={candidate.id}
                    candidate={candidate}
                    selected={state.selectedCandidate?.id === candidate.id}
                    busy={busy}
                    thumbnailUrl={candidateThumbUrl}
                    scoreLabel={c.score}
                    previewLabel={c.tryPreview}
                    insightLabels={insightLabels}
                    onPreview={handlePreview}
                  />
                ))
              ) : (
                <div className="panel-empty">{c.candidatesEmpty}</div>
              )}
            </div>
          </section>

          <section className="inspector-block">
            <div className="develop-tabs" role="tablist" aria-label="Develop controls">
              {developTabs.map((tab, index) => (
                <button
                  key={tab.label}
                  className={`tab-button${index === 0 ? " active" : ""}`}
                  type="button"
                  disabled={!tab.enabled}
                  title={tab.enabled ? tab.label : c.plannedFeature}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <div className="inspector-title compact-title">
              <span>{c.adjustments}</span>
              <small>{state.selectedCandidate?.name ?? c.basic}</small>
            </div>
            <AdjustmentsPanel
              adjustments={state.selectedCandidate?.adjustments ?? null}
              language={state.language}
              emptyLabel={c.adjustments}
              busy={busy}
              previewLabel={c.tryPreview}
              onChange={(adjustments) => dispatch({ type: "updateSelectedAdjustments", adjustments })}
              onPreview={() => {
                if (state.selectedCandidate) void handlePreview(state.selectedCandidate);
              }}
            />
          </section>

          <section className="inspector-block">
            <div className="inspector-title">
              <span>{c.tools}</span>
              <small>{c.planned}</small>
            </div>
            <div className="extension-grid">
              <div className="extension-slot">
                <Aperture size={16} aria-hidden="true" />
                <strong>{c.denoise}</strong>
                <span>{c.planned}</span>
              </div>
              <div className="extension-slot">
                <SlidersHorizontal size={16} aria-hidden="true" />
                <strong>{c.lensCorrection}</strong>
                <span>{c.planned}</span>
              </div>
              <div className={`extension-slot status-slot ${state.rawStatus?.available ? "ready" : "missing"}`} title={state.rawStatus?.message}>
                <BookOpen size={16} aria-hidden="true" />
                <strong>{c.rawSupport}</strong>
                <span>{rawStatusLabel}</span>
              </div>
            </div>
          </section>

          <section className="inspector-block">
            <div className="inspector-title">
              <span>{c.referenceLibrary}</span>
              <small>{state.references?.count ?? 0}</small>
            </div>
            <div className="reference-list">
              {referenceItems.length ? (
                referenceItems.map((item) => (
                  <article className="reference-card" key={item.id}>
                    <div className="reference-card-title">
                      <strong>{item.id}</strong>
                      <span className={item.source.exists ? "asset-state ready" : "asset-state missing"}>
                        {item.source.exists ? c.assetReady : c.assetMissing}
                      </span>
                    </div>
                    <div className="reference-row">
                      <span>{c.source}</span>
                      <strong>{item.source.path}</strong>
                    </div>
                    <div className="reference-row">
                      <span>{c.target}</span>
                      <strong>{item.targets[0]?.style ?? c.reference}</strong>
                    </div>
                    <div className="reference-row">
                      <span>{c.manifest}</span>
                      <strong>{item.manifest_path}</strong>
                    </div>
                  </article>
                ))
              ) : (
                <div className="panel-empty">{c.referenceEmpty}</div>
              )}
            </div>
          </section>

          <section className="inspector-block">
            <div className="inspector-title">
              <span>{c.metadata}</span>
            </div>
            <MetadataPanel
              analysis={state.analysis}
              language={state.language}
              emptyLabel={c.metadata}
              rawAnalysisLabel={c.rawAnalysis}
            />
          </section>
        </aside>
      </main>

      <footer className="statusbar">
        <span>{c.localOnly}</span>
        <span>{c.ai}: {aiStatusLabel}</span>
        <span>{c.aiConnection}: {aiConnectionLabel}</span>
        <span>{c.rawSupport}: {rawStatusLabel}</span>
        <span>{c.renderPipeline}: {c.sourceFirst}</span>
        <span>{loadedFilename}</span>
      </footer>
    </div>
  );
}

export default App;
