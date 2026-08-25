import type { AnalysisResult, BlockageType, JobResult, Severity } from "../types";

export function buildRecommendations(
  detected: boolean,
  type: BlockageType,
  severity: Severity
): string[] {
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

export function jobResultToAnalysis(job: JobResult): AnalysisResult {
  const s = job.summary;
  const total = Math.max(1, s.total_reaches);
  const full = s.full ?? s.blocked ?? 0;
  const partial = s.partial + (s.moderate ?? 0);
  const blockedOrPartial = full + partial;
  const blockageDetected = blockedOrPartial > 0 || (s.damage ?? 0) > 0;
  const affectedAreaPercent = s.total_reaches === 0 ? 0 : (blockedOrPartial / total) * 100;
  const blockedShare = full / total;

  let severity: Severity = "Low";
  if (blockedShare >= 0.3) severity = "High";
  else if (blockedOrPartial / total >= 0.15) severity = "Medium";

  let blockageType: BlockageType = "None";
  if ((s.damage ?? 0) > 0) blockageType = "Structural";
  else if (blockedOrPartial > 0) blockageType = "Vegetation";

  const classified = s.total_reaches;
  const confidence = classified === 0 ? 72 : Math.min(96, 82 + Math.min(14, classified / 2));

  return {
    blockageDetected,
    confidence,
    blockageType,
    severity,
    affectedAreaPercent,
    recommendations: buildRecommendations(blockageDetected, blockageType, severity),
    analyzedAt: new Date().toISOString(),
    imageId: job.prediction_id || job.job_id,
    job,
  };
}
