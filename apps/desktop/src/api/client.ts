import type {
  AiConnectionStatus,
  AiMode,
  AnalyzeImageResponse,
  PreviewResponse,
  RecommendResponse,
  ReferenceLibraryResponse,
  RawSupportStatus,
  StyleReferenceUploadResponse,
} from "./types";
import type { CorrectionAdjustments, CorrectionCandidate } from "@tonepilot/shared";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8765";

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (body.detail) {
        message = JSON.stringify(body.detail);
      }
    } catch {
      // Keep the HTTP status message.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export function absoluteApiUrl(path: string): string {
  return path.startsWith("http") ? path : `${API_BASE}${path}`;
}

export async function getAiStatus(): Promise<AiConnectionStatus> {
  const response = await fetch(`${API_BASE}/api/ai/status`);
  return parseJson<AiConnectionStatus>(response);
}

export async function getReferences(): Promise<ReferenceLibraryResponse> {
  const response = await fetch(`${API_BASE}/api/references`);
  return parseJson<ReferenceLibraryResponse>(response);
}

export async function uploadStyleReferences(files: File[]): Promise<StyleReferenceUploadResponse> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  const response = await fetch(`${API_BASE}/api/references/style-targets`, {
    method: "POST",
    body: formData,
  });
  return parseJson<StyleReferenceUploadResponse>(response);
}

export async function getRawStatus(): Promise<RawSupportStatus> {
  const response = await fetch(`${API_BASE}/api/raw/status`);
  return parseJson<RawSupportStatus>(response);
}

export async function analyzeImage(file: File): Promise<AnalyzeImageResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE}/api/images/analyze`, {
    method: "POST",
    body: formData,
  });
  return parseJson<AnalyzeImageResponse>(response);
}

export async function recommend(
  imageId: string,
  stylePrompt: string,
  strength: number,
  aiMode: AiMode = "auto",
  styleReferenceId?: string | null,
): Promise<RecommendResponse> {
  const response = await fetch(`${API_BASE}/api/recommend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      image_id: imageId,
      style_prompt: stylePrompt,
      strength,
      ai_mode: aiMode,
      style_reference_id: styleReferenceId,
    }),
  });
  return parseJson<RecommendResponse>(response);
}

export async function renderPreview(
  imageId: string,
  candidateId: string,
  adjustments: CorrectionAdjustments,
): Promise<PreviewResponse> {
  const response = await fetch(`${API_BASE}/api/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image_id: imageId, candidate_id: candidateId, adjustments }),
  });
  return parseJson<PreviewResponse>(response);
}

export async function downloadPreset(
  imageId: string,
  stylePrompt: string,
  candidate: CorrectionCandidate,
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/export/preset-json`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image_id: imageId, style_prompt: stylePrompt, candidate }),
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `tonepilot-${candidate.id}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function downloadRenderedImage(
  imageId: string,
  candidate: CorrectionCandidate,
  format: "jpeg" | "png" = "jpeg",
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/export/rendered-image`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      image_id: imageId,
      candidate_id: candidate.id,
      adjustments: candidate.adjustments,
      format,
    }),
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `tonepilot-${candidate.id}.${format === "jpeg" ? "jpg" : "png"}`;
  anchor.click();
  URL.revokeObjectURL(url);
}
