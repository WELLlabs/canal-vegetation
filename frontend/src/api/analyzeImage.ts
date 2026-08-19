import type { AnalysisResult, BlockageType, Severity } from "../types";

// Point this at your FastAPI/Flask service, e.g. via a .env value:
// VITE_API_BASE_URL=https://your-backend.example.gov
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string | undefined;
const USE_MOCK = !API_BASE_URL;

/**
 * Sends the drone image to the backend for analysis.
 *
 * Expected backend contract — POST {API_BASE_URL}/api/analyze
 *   Request:  multipart/form-data, field name "image"
 *   Response: 200 OK, JSON body matching `AnalysisResult`
 *
 * Example FastAPI response model:
 *   {
 *     "blockageDetected": true,
 *     "confidence": 92.4,
 *     "blockageType": "Vegetation",
 *     "severity": "High",
 *     "affectedAreaPercent": 38.5,
 *     "recommendations": ["Deploy manual desilting crew within 48 hours", ...],
 *     "analyzedAt": "2026-07-02T09:00:00Z",
 *     "imageId": "img_8f21ac"
 *   }
 */
export async function analyzeImage(
  file: File,
  onProgress?: (percent: number) => void
): Promise<AnalysisResult> {
  if (USE_MOCK) {
    return mockAnalyze(onProgress);
  }

  const formData = new FormData();
  formData.append("image", file);

  const response = await fetch(`${API_BASE_URL}/api/analyze`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Analysis failed (${response.status}): ${response.statusText}`);
  }

  return (await response.json()) as AnalysisResult;
}

/** Simulated backend response so the UI is fully demoable before the API is wired up. */
function mockAnalyze(onProgress?: (percent: number) => void): Promise<AnalysisResult> {
  return new Promise((resolve) => {
    let progress = 0;
    const interval = setInterval(() => {
      progress += Math.random() * 18 + 8;
      if (progress >= 100) {
        progress = 100;
        onProgress?.(progress);
        clearInterval(interval);

        const detected = Math.random() > 0.25;
        const types: BlockageType[] = ["Vegetation", "Silt", "Debris", "Structural"];
        const severities: Severity[] = ["Low", "Medium", "High"];
        const blockageType = detected ? types[Math.floor(Math.random() * types.length)] : "None";
        const severity = severities[Math.floor(Math.random() * severities.length)];
        const affected = detected ? Math.round((Math.random() * 45 + 10) * 10) / 10 : 0;

        resolve({
          blockageDetected: detected,
          confidence: Math.round((Math.random() * 12 + 85) * 10) / 10,
          blockageType,
          severity,
          affectedAreaPercent: affected,
          recommendations: buildRecommendations(detected, blockageType, severity),
          analyzedAt: new Date().toISOString(),
          imageId: `img_${Math.random().toString(36).slice(2, 8)}`,
        });
        return;
      }
      onProgress?.(progress);
    }, 260);
  });
}

function buildRecommendations(detected: boolean, type: BlockageType, severity: Severity): string[] {
  if (!detected) {
    return [
      "No obstruction identified along the surveyed reach.",
      "Schedule the next routine aerial pass in 30 days.",
      "Archive this image as a clean-channel baseline for change detection.",
    ];
  }

  const base: Record<BlockageType, string[]> = {
    Vegetation: [
      "Dispatch a weed-cutting crew to clear invasive growth from the channel bed.",
      "Flag the reach for a follow-up survey after clearance to confirm flow restoration.",
    ],
    Silt: [
      "Schedule mechanical desilting to restore design cross-section and carrying capacity.",
      "Inspect upstream erosion sources contributing sediment load.",
    ],
    Debris: [
      "Deploy a manual clearance team to remove floating and lodged debris.",
      "Install or inspect a trash rack upstream if recurring debris accumulation is observed.",
    ],
    Structural: [
      "Escalate to the civil engineering division for a structural integrity inspection.",
      "Restrict flow through the affected section until inspection is complete.",
    ],
    None: [],
  };

  const urgency =
    severity === "High"
      ? "Prioritize this reach for intervention within 48 hours — flow capacity is significantly compromised."
      : severity === "Medium"
      ? "Schedule intervention within the next maintenance cycle (7–14 days)."
      : "Monitor and include in the next routine maintenance round.";

  return [urgency, ...base[type]];
}
