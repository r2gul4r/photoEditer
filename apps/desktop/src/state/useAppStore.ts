import { useReducer } from "react";

import type {
  AiConnectionStatus,
  AiMode,
  AnalyzeImageResponse,
  RawSupportStatus,
  RecommendResponse,
  ReferenceLibraryResponse,
} from "../api/types";
import type { Language } from "../i18n";
import type { CorrectionAdjustments, CorrectionCandidate } from "@tonepilot/shared";

export type AppState = {
  language: Language;
  imageFile: File | null;
  originalUrl: string | null;
  analysis: AnalyzeImageResponse | null;
  recommendation: RecommendResponse | null;
  aiConnection: AiConnectionStatus | null;
  references: ReferenceLibraryResponse | null;
  rawStatus: RawSupportStatus | null;
  selectedCandidate: CorrectionCandidate | null;
  previewUrl: string | null;
  stylePrompt: string;
  aiMode: AiMode;
  strength: number;
  busyLabel: string | null;
  error: string | null;
};

type Action =
  | { type: "start"; label: string }
  | { type: "error"; error: string }
  | { type: "setImage"; file: File; originalUrl: string | null; label: string }
  | { type: "setAnalysis"; analysis: AnalyzeImageResponse; displayUrl?: string }
  | { type: "setAiConnection"; aiConnection: AiConnectionStatus }
  | { type: "setReferences"; references: ReferenceLibraryResponse }
  | { type: "setRawStatus"; rawStatus: RawSupportStatus }
  | { type: "setPrompt"; stylePrompt: string }
  | { type: "setAiMode"; aiMode: AiMode }
  | { type: "setStrength"; strength: number }
  | { type: "setLanguage"; language: Language }
  | { type: "setRecommendation"; recommendation: RecommendResponse }
  | { type: "setPreview"; candidate: CorrectionCandidate; previewUrl: string }
  | { type: "updateSelectedAdjustments"; adjustments: CorrectionAdjustments }
  | { type: "idle" };

const initialState: AppState = {
  language: "en",
  imageFile: null,
  originalUrl: null,
  analysis: null,
  recommendation: null,
  aiConnection: null,
  references: null,
  rawStatus: null,
  selectedCandidate: null,
  previewUrl: null,
  stylePrompt: "cool Japanese summer",
  aiMode: "auto",
  strength: 0.7,
  busyLabel: null,
  error: null,
};

function revokeIfObjectUrl(url: string | null) {
  if (url?.startsWith("blob:")) {
    URL.revokeObjectURL(url);
  }
}

function normalizeStrength(strength: number) {
  return Math.max(0, Math.min(1, Math.round(strength * 100) / 100));
}

function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case "start":
      return { ...state, busyLabel: action.label, error: null };
    case "error":
      return { ...state, busyLabel: null, error: action.error };
    case "setImage":
      revokeIfObjectUrl(state.originalUrl);
      return {
        ...initialState,
        imageFile: action.file,
        originalUrl: action.originalUrl,
        aiConnection: state.aiConnection,
        references: state.references,
        rawStatus: state.rawStatus,
        stylePrompt: state.stylePrompt,
        aiMode: state.aiMode,
        strength: state.strength,
        language: state.language,
        busyLabel: action.label,
      };
    case "setAnalysis":
      if (action.displayUrl && action.displayUrl !== state.originalUrl) {
        revokeIfObjectUrl(state.originalUrl);
      }
      return {
        ...state,
        analysis: action.analysis,
        originalUrl: action.displayUrl ?? state.originalUrl,
        busyLabel: null,
        error: null,
      };
    case "setAiConnection":
      return { ...state, aiConnection: action.aiConnection };
    case "setReferences":
      return { ...state, references: action.references };
    case "setRawStatus":
      return { ...state, rawStatus: action.rawStatus };
    case "setPrompt":
      return { ...state, stylePrompt: action.stylePrompt };
    case "setAiMode":
      return { ...state, aiMode: action.aiMode };
    case "setStrength":
      return { ...state, strength: normalizeStrength(action.strength) };
    case "setLanguage":
      return { ...state, language: action.language };
    case "setRecommendation":
      return {
        ...state,
        recommendation: action.recommendation,
        selectedCandidate: action.recommendation.candidates[0] ?? null,
        previewUrl: null,
        busyLabel: null,
        error: null,
      };
    case "setPreview":
      return {
        ...state,
        selectedCandidate: action.candidate,
        previewUrl: action.previewUrl,
        busyLabel: null,
        error: null,
      };
    case "updateSelectedAdjustments": {
      if (!state.selectedCandidate) {
        return state;
      }
      const selectedCandidate = {
        ...state.selectedCandidate,
        adjustments: action.adjustments,
      };
      const recommendation = state.recommendation
        ? {
            ...state.recommendation,
            candidates: state.recommendation.candidates.map((candidate) =>
              candidate.id === selectedCandidate.id ? selectedCandidate : candidate,
            ),
          }
        : state.recommendation;
      return {
        ...state,
        recommendation,
        selectedCandidate,
        previewUrl: null,
      };
    }
    case "idle":
      return { ...state, busyLabel: null };
    default:
      return state;
  }
}

export function useAppStore() {
  return useReducer(reducer, initialState);
}

