export type BlockageType = "Vegetation" | "Silt" | "Debris" | "Structural" | "None";
export type Severity = "Low" | "Medium" | "High";

/**
 * Shape returned by the backend (FastAPI/Flask) after analyzing an uploaded
 * drone image. Swap `analyzeImage` in `src/api/analyzeImage.ts` to call the
 * real endpoint — the rest of the UI only depends on this contract.
 */
export interface AnalysisResult {
  blockageDetected: boolean;
  confidence: number; // 0 - 100
  blockageType: BlockageType;
  severity: Severity;
  affectedAreaPercent: number; // 0 - 100
  recommendations: string[];
  analyzedAt: string; // ISO timestamp
  imageId: string;
  location?: string;
  coordinates?: { lat: number; lng: number };
}

export type WorkflowStage = "idle" | "preview" | "analyzing" | "results" | "error";
