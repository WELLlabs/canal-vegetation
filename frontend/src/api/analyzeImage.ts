import type { AnalysisResult } from "../types";
import { jobResultToAnalysis } from "./mapResult";
import {
  createProject,
  getJobStatus,
  getPrediction,
  getPredictionGeojson,
  startPrediction,
} from "./pipeline";

const POLL_MS = 2000;

/**
 * End-to-end Phase 1 flow against the real backend:
 * create project → upload/start prediction → poll job → load prediction + canonical GeoJSON.
 */
export async function analyzeImage(
  file: File,
  onProgress?: (percent: number, stage?: string) => void,
  extras?: { alignmentFiles?: File[] }
): Promise<AnalysisResult> {
  try {
    onProgress?.(4, "Creating project");
    const project = await createProject(file.name.replace(/\.[^.]+$/, "") || "Survey");

    onProgress?.(8, "Uploading orthomosaic");
    const job = await startPrediction(project.project_id, file, extras?.alignmentFiles);

    let status = job;
    while (status.status === "queued" || status.status === "running" || status.status === "processing") {
      const stage =
        status.status === "queued"
          ? "queued"
          : status.message || status.current_stage || "running";
      onProgress?.(Math.max(8, status.progress || 8), stage);
      await delay(POLL_MS);
      status = await getJobStatus(status.job_id);
    }

    if (status.status === "failed") {
      throw new Error(status.error || status.message || "Pipeline failed");
    }

    const predictionId = status.prediction_id || job.prediction_id;
    if (!predictionId) throw new Error("Prediction id missing from job");

    onProgress?.(96, "Loading results");
    const [result, geojson] = await Promise.all([
      getPrediction(predictionId),
      getPredictionGeojson(predictionId),
    ]);

    // Canonical GeoJSON endpoint is the source of truth for the map/table.
    result.geojson = geojson;
    result.features = geojson.features ?? [];
    if (geojson.metadata) {
      result.pipeline_mode = result.pipeline_mode || geojson.metadata.pipeline_mode;
      result.model_version = result.model_version || geojson.metadata.model_version;
      result.label_source = result.label_source || geojson.metadata.label_source;
    }

    onProgress?.(100, "completed");
    return jobResultToAnalysis(result);
  } catch (err) {
    if (err instanceof TypeError) {
      throw new Error("Cannot reach the API. Start FastAPI on port 8000 (Vite proxies /api).");
    }
    throw err;
  }
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
