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
import { useEffect, useRef, useState } from "react";
import type { ReactElement } from "react";

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
  uploadStyleReferences,
} from "./api/client";
import { AdjustmentsPanel, type AdjustmentGroup } from "./components/AdjustmentsPanel";
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
import type { CorrectionAdjustments, CorrectionCandidate, CropAspect } from "@tonepilot/shared";

type ModuleKey = "library" | "edit" | "ai" | "reference" | "export";
type ImageViewMode = "original" | "preview" | "compare" | "grid";
type ZoomMode = "fit" | "actual";
type ExportFormat = "jpeg" | "png";

function App() {
  const [state, dispatch] = useAppStore();
  const c = copy[state.language];
  const topFileInputRef = useRef<HTMLInputElement | null>(null);
  const styleReferenceInputRef = useRef<HTMLInputElement | null>(null);
  const aiSectionRef = useRef<HTMLElement | null>(null);
  const adjustmentsSectionRef = useRef<HTMLElement | null>(null);
  const referenceSectionRef = useRef<HTMLElement | null>(null);
  const exportSectionRef = useRef<HTMLElement | null>(null);
  const filmstripRef = useRef<HTMLDivElement | null>(null);
  const [activeModule, setActiveModule] = useState<ModuleKey>("edit");
  const [activeDevelopTab, setActiveDevelopTab] = useState<AdjustmentGroup>("basic");
  const [activeImageView, setActiveImageView] = useState<ImageViewMode>("original");
  const [zoomMode, setZoomMode] = useState<ZoomMode>("fit");
  const [cropGuideEnabled, setCropGuideEnabled] = useState(false);
  const [cropAspect, setCropAspect] = useState<CropAspect>("original");
  const [rotation, setRotation] = useState(0);
  const [exportFormat, setExportFormat] = useState<ExportFormat>("jpeg");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [workspaceCollapsed, setWorkspaceCollapsed] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [rating, setRating] = useState(0);
  const [flagged, setFlagged] = useState(false);
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

  const moduleItems: Array<{ key: ModuleKey; label: string; icon: ReactElement }> = [
    { key: "library", label: c.library, icon: <Images size={19} aria-hidden="true" /> },
    { key: "edit", label: c.edit, icon: <SlidersHorizontal size={19} aria-hidden="true" /> },
    { key: "ai", label: c.ai, icon: <Sparkles size={19} aria-hidden="true" /> },
    { key: "reference", label: c.reference, icon: <BookOpen size={19} aria-hidden="true" /> },
    { key: "export", label: c.export, icon: <Download size={19} aria-hidden="true" /> },
  ];

  const developTabs: Array<{ key: AdjustmentGroup; label: string }> = [
    { key: "basic", label: c.basic },
    { key: "toneCurve", label: c.toneCurve },
    { key: "color", label: c.color },
    { key: "detail", label: c.detail },
    { key: "masks", label: c.masks },
  ];
  const aiModeOptions: Array<{ value: AiMode; label: string }> = [
    { value: "auto", label: c.aiModeAuto },
    { value: "codex", label: c.aiModeCodex },
    { value: "rules", label: c.aiModeRules },
  ];
  const cropAspects: CropAspect[] = ["original", "square", "landscape", "portrait"];
  const cropAspectLabels: Record<CropAspect, string> = {
    original: c.cropOriginal,
    square: c.cropSquare,
    landscape: c.cropLandscape,
    portrait: c.cropPortrait,
  };
  const activeCropAspect = cropGuideEnabled ? cropAspect : "original";
  const selectedNoiseReduction = state.selectedCandidate?.adjustments.noise_reduction ?? 0;
  const selectedVignetteCorrection = state.selectedCandidate?.adjustments.vignette_correction ?? 0;
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

  useEffect(() => {
    if (!state.originalUrl) {
      setActiveImageView("original");
      setCropGuideEnabled(false);
      setCropAspect("original");
      setRotation(0);
      return;
    }
    setActiveImageView(state.previewUrl ? "compare" : "original");
  }, [state.originalUrl, state.previewUrl]);

  useEffect(() => {
    function updateFullscreenState() {
      setIsFullscreen(Boolean(document.fullscreenElement));
    }

    document.addEventListener("fullscreenchange", updateFullscreenState);
    return () => {
      document.removeEventListener("fullscreenchange", updateFullscreenState);
    };
  }, []);

  function openFilePicker() {
    setMenuOpen(false);
    setSettingsOpen(false);
    topFileInputRef.current?.click();
  }

  function scrollToSection(section: HTMLElement | null) {
    section?.scrollIntoView({ block: "start", behavior: "smooth" });
  }

  function clampPercent(value: number) {
    return Math.max(0, Math.min(100, Math.round(value)));
  }

  function candidateForPreview(candidate: CorrectionCandidate): CorrectionCandidate {
    return {
      ...candidate,
      adjustments: {
        ...candidate.adjustments,
        rotation_degrees: 0,
        crop_aspect: "original",
      },
    };
  }

  function candidateForExport(candidate: CorrectionCandidate): CorrectionCandidate {
    return {
      ...candidate,
      adjustments: {
        ...candidate.adjustments,
        rotation_degrees: rotation,
        crop_aspect: activeCropAspect,
      },
    };
  }

  function handleCropCycle() {
    if (!state.originalUrl) return;
    const currentIndex = cropGuideEnabled ? cropAspects.indexOf(cropAspect) : 0;
    const nextAspect = cropAspects[(currentIndex + 1) % cropAspects.length];
    setCropAspect(nextAspect);
    setCropGuideEnabled(nextAspect !== "original");
  }

  function applyToolAdjustments(patch: Partial<CorrectionAdjustments>, tab: AdjustmentGroup = "detail") {
    if (!state.selectedCandidate || !imageId || busy) return;
    const nextCandidate = {
      ...state.selectedCandidate,
      adjustments: {
        ...state.selectedCandidate.adjustments,
        ...patch,
      },
    };
    dispatch({ type: "updateSelectedAdjustments", adjustments: nextCandidate.adjustments });
    setActiveDevelopTab(tab);
    setActiveModule("edit");
    void handlePreview(nextCandidate);
  }

  function handleApplyDenoise() {
    const adjustments = state.selectedCandidate?.adjustments;
    if (!adjustments) return;
    applyToolAdjustments({
      noise_reduction: clampPercent((adjustments.noise_reduction ?? 0) + 20),
      texture: Math.min(adjustments.texture, -2),
      clarity: Math.min(adjustments.clarity, 0),
    });
  }

  function handleApplyLensCorrection() {
    const adjustments = state.selectedCandidate?.adjustments;
    if (!adjustments) return;
    applyToolAdjustments({
      vignette_correction: clampPercent((adjustments.vignette_correction ?? 0) + 18),
    });
  }

  async function refreshRawSupport() {
    try {
      const rawStatus = await getRawStatus();
      dispatch({ type: "setRawStatus", rawStatus });
    } catch (error) {
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
  }

  function handleModuleSelect(module: ModuleKey) {
    setActiveModule(module);
    setWorkspaceCollapsed(false);
    if (module === "library") {
      filmstripRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    } else if (module === "reference") {
      scrollToSection(referenceSectionRef.current);
    } else if (module === "ai") {
      scrollToSection(aiSectionRef.current);
    } else if (module === "edit") {
      scrollToSection(adjustmentsSectionRef.current);
    } else {
      scrollToSection(exportSectionRef.current);
    }
  }

  function handleDevelopTab(tab: AdjustmentGroup) {
    setActiveDevelopTab(tab);
    setActiveModule("edit");
    scrollToSection(adjustmentsSectionRef.current);
  }

  function handleResetSession() {
    dispatch({ type: "resetSession" });
    setActiveImageView("original");
    setActiveDevelopTab("basic");
    setActiveModule("edit");
    setZoomMode("fit");
    setCropGuideEnabled(false);
    setCropAspect("original");
    setRotation(0);
    setExportFormat("jpeg");
    setMenuOpen(false);
    setSettingsOpen(false);
    setWorkspaceCollapsed(false);
    setRating(0);
    setFlagged(false);
  }

  async function handleToggleFullscreen() {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      } else {
        await document.documentElement.requestFullscreen();
      }
    } catch {
      setIsFullscreen((value) => !value);
    }
  }

  async function handleFile(file: File) {
    setWorkspaceCollapsed(false);
    setMenuOpen(false);
    setSettingsOpen(false);
    setCropGuideEnabled(false);
    setCropAspect("original");
    setRotation(0);
    setRating(0);
    setFlagged(false);
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

  function renderPhotoStageContent() {
    const imageStyle = {
      transform: `rotate(${rotation}deg) scale(${zoomMode === "actual" ? 1.12 : 1})`,
      transition: "transform 160ms ease",
    };

    if (!state.originalUrl) {
      return (
        <div className="empty-preview stage-empty-bg">
          {busy ? <Loader2 size={28} aria-hidden="true" /> : null}
          {busy ? <span>{state.busyLabel ?? c.noPhoto}</span> : null}
        </div>
      );
    }

    if (activeImageView === "grid") {
      return (
        <div className="image-grid-view">
          <ImagePreview
            imageUrl={state.originalUrl}
            filename={c.original}
            emptyLabel={c.noPhoto}
            altLabel={c.originalPhoto}
            imageStyle={imageStyle}
          />
          <ImagePreview
            imageUrl={state.previewUrl}
            filename={state.previewUrl ? c.preview : undefined}
            emptyLabel={c.noPreview}
            altLabel={c.preview}
            imageStyle={imageStyle}
          />
        </div>
      );
    }

    if (activeImageView === "compare" && state.previewUrl) {
      return (
        <BeforeAfterView
          originalUrl={state.originalUrl}
          previewUrl={state.previewUrl}
          originalLabel={c.original}
          previewLabel={c.preview}
          imageStyle={imageStyle}
        />
      );
    }

    const showingPreview = activeImageView === "preview" && state.previewUrl;
    return (
      <ImagePreview
        imageUrl={showingPreview ? state.previewUrl : state.originalUrl}
        filename={showingPreview ? c.preview : loadedFilename}
        emptyLabel={c.noPhoto}
        altLabel={showingPreview ? c.preview : c.originalPhoto}
        imageStyle={imageStyle}
      />
    );
  }

  async function handleRecommend() {
    if (!imageId) return;
    dispatch({ type: "start", label: c.recommendBusy });
    try {
      const response = await recommend(
        imageId,
        state.stylePrompt,
        state.strength,
        state.aiMode,
        state.styleReference?.style_reference_id ?? null,
      );
      dispatch({ type: "setRecommendation", recommendation: response });
    } catch (error) {
      dispatch({ type: "error", error: error instanceof Error ? error.message : c.recommendError });
    }
  }

  async function handlePreview(candidate: CorrectionCandidate) {
    if (!imageId) return;
    dispatch({ type: "start", label: c.previewBusy });
    try {
      const previewCandidate = candidateForPreview(candidate);
      const response = await renderPreview(imageId, previewCandidate.id, previewCandidate.adjustments);
      dispatch({ type: "setPreview", candidate: previewCandidate, previewUrl: absoluteApiUrl(response.preview_url) });
    } catch (error) {
      dispatch({ type: "error", error: error instanceof Error ? error.message : c.previewError });
    }
  }

  async function handlePresetExport() {
    if (!imageId || !state.selectedCandidate) return;
    dispatch({ type: "start", label: c.jsonBusy });
    try {
      await downloadPreset(imageId, state.stylePrompt, candidateForExport(state.selectedCandidate));
      dispatch({ type: "idle" });
    } catch (error) {
      dispatch({ type: "error", error: error instanceof Error ? error.message : c.jsonError });
    }
  }

  async function handleImageExport(format: ExportFormat = exportFormat) {
    if (!imageId || !state.selectedCandidate) return;
    dispatch({ type: "start", label: c.imageBusy });
    try {
      await downloadRenderedImage(imageId, candidateForExport(state.selectedCandidate), format);
      dispatch({ type: "idle" });
    } catch (error) {
      dispatch({ type: "error", error: error instanceof Error ? error.message : c.imageError });
    }
  }

  async function handleStyleReferenceFiles(files: FileList | null) {
    const selectedFiles = Array.from(files ?? []);
    if (!selectedFiles.length) return;
    dispatch({ type: "start", label: c.referenceBusy });
    setActiveModule("reference");
    try {
      const response = await uploadStyleReferences(selectedFiles);
      dispatch({ type: "setStyleReference", styleReference: response.reference });
    } catch (error) {
      dispatch({ type: "error", error: error instanceof Error ? error.message : c.referenceError });
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
          <button className="button" type="button" onClick={openFilePicker}>
            <FolderOpen size={16} aria-hidden="true" />
            {c.openPhoto}
          </button>
          <button
            className="button"
            type="button"
            disabled={!state.selectedCandidate || busy}
            onClick={() => void handleImageExport(exportFormat)}
          >
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
          <button
            className={`icon-button${settingsOpen ? " active" : ""}`}
            type="button"
            title={c.settings}
            aria-expanded={settingsOpen}
            onClick={() => {
              setSettingsOpen((value) => !value);
              setMenuOpen(false);
            }}
          >
            <Settings size={18} aria-hidden="true" />
          </button>
          <span className="topbar-divider" aria-hidden="true" />
          <button
            className={`icon-button quiet${menuOpen ? " active" : ""}`}
            type="button"
            title={c.menu}
            aria-expanded={menuOpen}
            onClick={() => {
              setMenuOpen((value) => !value);
              setSettingsOpen(false);
            }}
          >
            <Menu size={18} aria-hidden="true" />
          </button>
          <button
            className="icon-button quiet window-control"
            type="button"
            title={workspaceCollapsed ? c.restoreWorkspace : c.minimizeWorkspace}
            onClick={() => setWorkspaceCollapsed((value) => !value)}
          >
            <Minus size={16} aria-hidden="true" />
          </button>
          <button
            className="icon-button quiet window-control"
            type="button"
            title={isFullscreen ? c.exitFullscreen : c.fullscreen}
            onClick={() => void handleToggleFullscreen()}
          >
            <Square size={14} aria-hidden="true" />
          </button>
          <button className="icon-button quiet window-control" type="button" title={c.closeSession} onClick={handleResetSession}>
            <X size={16} aria-hidden="true" />
          </button>
          {settingsOpen ? (
            <div className="floating-panel settings-floating" role="dialog" aria-label={c.settings}>
              <div className="floating-panel-header">
                <strong>{c.settings}</strong>
                <button className="icon-button quiet" type="button" title={c.closePanel} onClick={() => setSettingsOpen(false)}>
                  <X size={15} aria-hidden="true" />
                </button>
              </div>
              <div className="settings-grid">
                <span>{c.language}</span>
                <div className="segmented-buttons">
                  {(["en", "ko"] as const).map((language) => (
                    <button
                      key={language}
                      className={`mode-button${state.language === language ? " active" : ""}`}
                      type="button"
                      onClick={() => dispatch({ type: "setLanguage", language })}
                    >
                      {language.toUpperCase()}
                    </button>
                  ))}
                </div>
                <span>{c.aiMode}</span>
                <div className="segmented-buttons">
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
                <span>{c.rawSupport}</span>
                <strong>{rawStatusLabel}</strong>
              </div>
            </div>
          ) : null}
          {menuOpen ? (
            <div className="floating-panel menu-floating" role="dialog" aria-label={c.commandMenu}>
              <div className="floating-panel-header">
                <strong>{c.commandMenu}</strong>
                <button className="icon-button quiet" type="button" title={c.closePanel} onClick={() => setMenuOpen(false)}>
                  <X size={15} aria-hidden="true" />
                </button>
              </div>
              <div className="command-list">
                <button className="button full" type="button" onClick={openFilePicker}>
                  <FolderOpen size={16} aria-hidden="true" />
                  {c.openPhoto}
                </button>
                <button
                  className="button full"
                  type="button"
                  disabled={!imageId || busy}
                  onClick={() => {
                    setMenuOpen(false);
                    void handleRecommend();
                  }}
                >
                  <Sparkles size={16} aria-hidden="true" />
                  {c.generate}
                </button>
                <button
                  className="button full"
                  type="button"
                  disabled={!state.previewUrl}
                  onClick={() => {
                    setActiveImageView("compare");
                    setMenuOpen(false);
                  }}
                >
                  <Columns2 size={16} aria-hidden="true" />
                  {c.compare}
                </button>
                <button
                  className="button full"
                  type="button"
                  disabled={!state.selectedCandidate || busy}
                  onClick={() => {
                    setMenuOpen(false);
                    void handleImageExport(exportFormat);
                  }}
                >
                  <Download size={16} aria-hidden="true" />
                  {c.exportImage}
                </button>
                <button className="button full" type="button" disabled={!state.selectedCandidate || busy} onClick={handlePresetExport}>
                  <FileJson size={16} aria-hidden="true" />
                  {c.exportJson}
                </button>
                <button className="button ghost full" type="button" onClick={handleResetSession}>
                  <X size={16} aria-hidden="true" />
                  {c.resetSession}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </header>

      {workspaceCollapsed ? (
        <main className="workspace-collapsed">
          <div>
            <strong>TonePilot Local</strong>
            <span>{loadedFilename}</span>
          </div>
          <button className="button primary" type="button" onClick={() => setWorkspaceCollapsed(false)}>
            {c.restoreWorkspace}
          </button>
        </main>
      ) : (
      <main className="workspace editor-workspace">
        <nav className="module-rail" aria-label="Editor modules">
          {moduleItems.map((item) => (
            <button
              key={item.key}
              className={`module-button${activeModule === item.key ? " active" : ""}`}
              type="button"
              title={item.label}
              onClick={() => handleModuleSelect(item.key)}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <section className="canvas-pane">
          <div className="editor-toolbar">
            <div className="toolbar-group">
              <button
                className={`tool-chip${cropGuideEnabled ? " active" : ""}`}
                type="button"
                disabled={!state.originalUrl}
                title={cropAspectLabels[activeCropAspect]}
                onClick={handleCropCycle}
              >
                <Crop size={15} aria-hidden="true" />
                {c.crop}
              </button>
              <button
                className="tool-chip"
                type="button"
                disabled={!state.originalUrl}
                title={c.rotateClockwise}
                onClick={() => setRotation((value) => (value + 90) % 360)}
              >
                <RotateCw size={15} aria-hidden="true" />
                {c.rotate}
              </button>
              <button
                className={`tool-chip${activeImageView === "compare" ? " active" : ""}`}
                type="button"
                disabled={!state.previewUrl}
                title={state.previewUrl ? c.compare : c.noPreview}
                onClick={() => setActiveImageView(activeImageView === "compare" ? "preview" : "compare")}
              >
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
            {renderPhotoStageContent()}
            {cropGuideEnabled && state.originalUrl ? (
              <div className={`crop-guide ${cropAspect}`} aria-hidden="true">
                <span />
                <span />
                <span />
                <span />
              </div>
            ) : null}
            {activeDevelopTab === "masks" && state.originalUrl ? <div className="mask-guide" aria-hidden="true" /> : null}
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
              <button
                className={`mini-tool${activeImageView === "grid" ? " active" : ""}`}
                type="button"
                disabled={!state.originalUrl}
                title={c.gridView}
                onClick={() => setActiveImageView("grid")}
              >
                <Grid2X2 size={15} aria-hidden="true" />
              </button>
              <button
                className={`mini-tool${activeImageView === "compare" ? " active" : ""}`}
                type="button"
                disabled={!state.previewUrl}
                title={state.previewUrl ? c.compare : c.noPreview}
                onClick={() => setActiveImageView("compare")}
              >
                <Columns2 size={15} aria-hidden="true" />
              </button>
              <button
                className={`zoom-chip${zoomMode === "fit" ? " active" : ""}`}
                type="button"
                disabled={!state.originalUrl}
                onClick={() => setZoomMode("fit")}
              >
                {c.fitZoom}
              </button>
              <button
                className={`zoom-chip${zoomMode === "actual" ? " active" : ""}`}
                type="button"
                disabled={!state.originalUrl}
                onClick={() => setZoomMode("actual")}
              >
                {c.actualZoom}
              </button>
            </div>
            <div className="rating-strip" aria-label="Rating">
              {[0, 1, 2, 3, 4].map((value) => (
                <button
                  key={value}
                  className={`rating-button${rating > value ? " active" : ""}`}
                  type="button"
                  disabled={!state.originalUrl}
                  onClick={() => setRating(rating === value + 1 ? 0 : value + 1)}
                >
                  <Star size={14} aria-hidden="true" fill={rating > value ? "currentColor" : "none"} />
                </button>
              ))}
              <button
                className={`rating-button${flagged ? " active" : ""}`}
                type="button"
                disabled={!state.originalUrl}
                onClick={() => setFlagged((value) => !value)}
              >
                <Flag size={14} aria-hidden="true" fill={flagged ? "currentColor" : "none"} />
              </button>
            </div>
            <div className="capture-info">
              {captureInfo.length ? captureInfo.map((item) => <span key={item}>{item}</span>) : <span>{c.noPhoto}</span>}
            </div>
          </div>

          {state.error ? <div className="error-box">{state.error}</div> : null}

          <div className="filmstrip" ref={filmstripRef}>
            <div className="strip-header">
              <span>{c.filmstrip}</span>
              <small>{c.references}: {state.references?.count ?? 0}</small>
            </div>
            <div className="strip-list">
              <button
                className={`strip-thumb${activeImageView === "original" ? " active" : ""}`}
                type="button"
                disabled={!state.originalUrl}
                onClick={() => setActiveImageView("original")}
              >
                {state.originalUrl ? <img src={state.originalUrl} alt={loadedFilename} /> : <span className="thumb-placeholder" />}
                <span>{c.original}</span>
              </button>
              <button
                className={`strip-thumb${activeImageView === "preview" || activeImageView === "compare" ? " active" : ""}`}
                type="button"
                disabled={!state.previewUrl}
                onClick={() => setActiveImageView("preview")}
              >
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

          <section className="inspector-block" ref={aiSectionRef}>
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

          <section className="inspector-block" ref={adjustmentsSectionRef}>
            <div className="develop-tabs" role="tablist" aria-label="Develop controls">
              {developTabs.map((tab) => (
                <button
                  key={tab.key}
                  className={`tab-button${activeDevelopTab === tab.key ? " active" : ""}`}
                  type="button"
                  title={tab.label}
                  onClick={() => handleDevelopTab(tab.key)}
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
              group={activeDevelopTab}
              busy={busy}
              previewLabel={c.tryPreview}
              onChange={(adjustments) => dispatch({ type: "updateSelectedAdjustments", adjustments })}
              onPreview={() => {
                if (state.selectedCandidate) void handlePreview(state.selectedCandidate);
              }}
            />
          </section>

          <section className="inspector-block" ref={exportSectionRef}>
            <div className="inspector-title">
              <span>{c.exportPanel}</span>
              <small>{exportFormat.toUpperCase()}</small>
            </div>
            <div className="control-stack">
              <div className="mode-toggle">
                <span>{c.fileFormat}</span>
                <div>
                  {(["jpeg", "png"] as const).map((format) => (
                    <button
                      key={format}
                      className={`mode-button${exportFormat === format ? " active" : ""}`}
                      type="button"
                      onClick={() => setExportFormat(format)}
                    >
                      {format === "jpeg" ? c.jpeg : c.png}
                    </button>
                  ))}
                </div>
              </div>
              <button
                className="button primary full"
                type="button"
                disabled={!state.selectedCandidate || busy}
                onClick={() => void handleImageExport(exportFormat)}
              >
                <Download size={16} aria-hidden="true" />
                {exportFormat === "jpeg" ? c.saveJpeg : c.savePng}
              </button>
              <button className="button ghost full" type="button" disabled={!state.selectedCandidate || busy} onClick={handlePresetExport}>
                <FileJson size={16} aria-hidden="true" />
                {c.exportJson}
              </button>
            </div>
          </section>

          <section className="inspector-block">
            <div className="inspector-title">
              <span>{c.tools}</span>
              <small>{c.ready}</small>
            </div>
            <div className="extension-grid">
              <button
                className={`extension-slot action-slot${selectedNoiseReduction > 0 ? " ready" : ""}`}
                type="button"
                disabled={!state.selectedCandidate || busy}
                onClick={handleApplyDenoise}
              >
                <Aperture size={16} aria-hidden="true" />
                <strong>{c.denoise}</strong>
                <span>{selectedNoiseReduction > 0 ? `${c.applied} ${Math.round(selectedNoiseReduction)}%` : c.denoiseApply}</span>
              </button>
              <button
                className={`extension-slot action-slot${selectedVignetteCorrection > 0 ? " ready" : ""}`}
                type="button"
                disabled={!state.selectedCandidate || busy}
                onClick={handleApplyLensCorrection}
              >
                <SlidersHorizontal size={16} aria-hidden="true" />
                <strong>{c.lensCorrection}</strong>
                <span>
                  {selectedVignetteCorrection > 0 ? `${c.applied} ${Math.round(selectedVignetteCorrection)}%` : c.lensApply}
                </span>
              </button>
              <button
                className={`extension-slot status-slot ${state.rawStatus?.available ? "ready" : "missing"}`}
                type="button"
                title={state.rawStatus?.message}
                onClick={() => void refreshRawSupport()}
              >
                <BookOpen size={16} aria-hidden="true" />
                <strong>{c.rawSupport}</strong>
                <span>{rawStatusLabel}</span>
              </button>
            </div>
          </section>

          <section className="inspector-block" ref={referenceSectionRef}>
            <div className="inspector-title">
              <span>{c.referenceLibrary}</span>
              <small>{state.references?.count ?? 0}</small>
            </div>
            <input
              ref={styleReferenceInputRef}
              className="hidden-file-input"
              type="file"
              accept="image/jpeg,image/png,.jpg,.jpeg,.png"
              multiple
              onChange={(event) => {
                void handleStyleReferenceFiles(event.target.files);
                event.currentTarget.value = "";
              }}
            />
            <div className="style-reference-target">
              <button
                className="button full"
                type="button"
                disabled={busy}
                onClick={() => styleReferenceInputRef.current?.click()}
              >
                <Images size={16} aria-hidden="true" />
                {c.addStyleReferences}
              </button>
              {state.styleReference ? (
                <div className="style-reference-summary">
                  <strong>{state.styleReference.count} {c.referenceImages}</strong>
                  <span>{state.styleReference.summary}</span>
                </div>
              ) : (
                <div className="panel-empty compact-empty">{c.styleReferenceEmpty}</div>
              )}
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
      )}

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
