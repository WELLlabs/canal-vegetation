import type { JobResult } from "../types";
import { API_BASE_URL, apiUrl, readError } from "./config";

export interface JobStatusResponse {
  job_id: string;
  status: string;
  progress: number;
  current_stage: string;
  error: string | null;
  failed_stage: string | null;
  prediction_id?: string | null;
  message?: string | null;
}

export async function createProject(name = "Survey"): Promise<{ project_id: string; name: string }> {
  const response = await fetch(apiUrl("/api/v1/projects"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as { project_id: string; name: string };
}

export async function startPrediction(
  projectId: string,
  ortho: File,
  alignmentFiles?: File[]
): Promise<JobStatusResponse> {
  const form = new FormData();
  form.append("ortho_file", ortho);
  if (alignmentFiles?.length) {
    for (const f of alignmentFiles) {
      form.append("alignment_files", f);
    }
  }
  const response = await fetch(apiUrl(`/api/v1/projects/${projectId}/predictions`), {
    method: "POST",
    body: form,
  });
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as JobStatusResponse;
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const response = await fetch(apiUrl(`/api/v1/jobs/${jobId}`));
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as JobStatusResponse;
}

export async function getPrediction(predictionId: string): Promise<JobResult> {
  const response = await fetch(apiUrl(`/api/v1/predictions/${predictionId}`));
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as JobResult;
}

export async function getPredictionGeojson(
  predictionId: string
): Promise<JobResult["geojson"]> {
  const response = await fetch(apiUrl(`/api/v1/predictions/${predictionId}/geojson`));
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as JobResult["geojson"];
}

export function predictionImageUrl(predictionId: string, relpath: string): string {
  const name = relpath.replace(/^images\//, "");
  return apiUrl(`/api/v1/predictions/${predictionId}/images/${name}`);
}


export function orthoPreviewUrl(predictionId: string): string {
  return apiUrl(`/api/v1/predictions/${predictionId}/ortho`);
}

export { API_BASE_URL };
