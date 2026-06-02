import { useReducer } from "react";

import type { AnalyzeImageResponse, RecommendResponse } from "../api/types";
import type { CorrectionCandidate } from "@tonepilot/shared";

export type AppState = {
  imageFile: File | null;
  originalUrl: string | null;
  analysis: AnalyzeImageResponse | null;
  recommendation: RecommendResponse | null;
  selectedCandidate: CorrectionCandidate | null;
  previewUrl: string | null;
  stylePrompt: string;
  strength: number;
  busyLabel: string | null;
  error: string | null;
};

type Action =
  | { type: "start"; label: string }
  | { type: "error"; error: string }
  | { type: "setImage"; file: File; originalUrl: string }
  | { type: "setAnalysis"; analysis: AnalyzeImageResponse }
  | { type: "setPrompt"; stylePrompt: string }
  | { type: "setStrength"; strength: number }
  | { type: "setRecommendation"; recommendation: RecommendResponse }
  | { type: "setPreview"; candidate: CorrectionCandidate; previewUrl: string }
  | { type: "idle" };

const initialState: AppState = {
  imageFile: null,
  originalUrl: null,
  analysis: null,
  recommendation: null,
  selectedCandidate: null,
  previewUrl: null,
  stylePrompt: "시원한 일본 여름 느낌",
  strength: 0.7,
  busyLabel: null,
  error: null,
};

function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case "start":
      return { ...state, busyLabel: action.label, error: null };
    case "error":
      return { ...state, busyLabel: null, error: action.error };
    case "setImage":
      if (state.originalUrl) {
        URL.revokeObjectURL(state.originalUrl);
      }
      return {
        ...initialState,
        imageFile: action.file,
        originalUrl: action.originalUrl,
        stylePrompt: state.stylePrompt,
        strength: state.strength,
        busyLabel: "이미지 분석 중",
      };
    case "setAnalysis":
      return { ...state, analysis: action.analysis, busyLabel: null, error: null };
    case "setPrompt":
      return { ...state, stylePrompt: action.stylePrompt };
    case "setStrength":
      return { ...state, strength: action.strength };
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
    case "idle":
      return { ...state, busyLabel: null };
    default:
      return state;
  }
}

export function useAppStore() {
  return useReducer(reducer, initialState);
}

