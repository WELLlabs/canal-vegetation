export type BlockageType = "Vegetation" | "Silt" | "Debris" | "Structural" | "None";
export type Severity = "Low" | "Medium" | "High";
export type JobStatusValue = "queued" | "running" | "processing" | "completed" | "failed";

export interface PipelineSummary {
  total_reaches: number;
  clear: number;
  partial: number;
  moderate?: number;
  full?: number;
  blocked?: number;
  silt_low?: number;
  silt_medium?: number;
  silt_high?: number;
  damage?: number;
}

export interface ReachProperties {
  reach_id: string;
  tile_id?: string;
  canal_name?: string;
  canal_type?: string;
  chainage_m?: number;
  blockage_status?: string;
  blockage_pct?: number;
  structural_damage?: boolean;
  centroid_lon?: number;
  centroid_lat?: number;
  thumbnail_relpath?: string;
  status?: string;
  blockage_percentage?: number;
  damage?: boolean;
  silt_status?: string;
  chainage?: number;
  image_path?: string;
}

export interface ReachFeature {
  type: "Feature";
  geometry: Record<string, unknown> | null;
  properties: ReachProperties;
}

export interface JobResult {
  job_id: string;
  prediction_id?: string;
  project_id?: string;
  status: string;
  pipeline_mode?: string;
  model_version?: string;
  label_source?: string;
  summary: PipelineSummary;
  outputs: Record<string, string | null>;
  geojson: {
    type: "FeatureCollection";
    metadata?: {
      project_id?: string;
      prediction_id?: string;
      model_version?: string;
      pipeline_mode?: string;
      label_source?: string;
      /** Leaflet LatLngBounds: [[south, west], [north, east]] EPSG:4326 */
      ortho_bounds?: [[number, number], [number, number]];
    };
    features: ReachFeature[];
  };
  features: ReachFeature[];
}

export interface AnalysisResult {
  blockageDetected: boolean;
  confidence: number;
  blockageType: BlockageType;
  severity: Severity;
  affectedAreaPercent: number;
  recommendations: string[];
  analyzedAt: string;
  imageId: string;
  location?: string;
  coordinates?: { lat: number; lng: number };
  job?: JobResult;
}

export type WorkflowStage = "idle" | "preview" | "analyzing" | "results" | "error";

export const STAGE_LABELS: Record<string, string> = {
  upload: "Uploading files",
  "Creating project": "Creating project",
  "Uploading orthomosaic": "Uploading orthomosaic",
  "Loading results": "Loading results",
  queued: "Queued — waiting for worker",
  running: "Running pipeline",
  processing: "Processing",
  completed: "Completed",
  failed: "Failed",
};
