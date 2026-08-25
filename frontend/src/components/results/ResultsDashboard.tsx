import { useCallback, useMemo, useState } from "react";
import { Download, Gauge, LayoutGrid, Percent, ScanEye } from "lucide-react";
import type { AnalysisResult, ReachFeature } from "../../types";
import StatusBadge from "./StatusBadge";
import ConfidenceGauge from "./ConfidenceGauge";
import SeverityMeter from "./SeverityMeter";
import InfoCard from "./InfoCard";
import RecommendationsList from "./RecommendationsList";
import { downloadReport } from "../../utils/generateReport";
import ReachTable from "./ReachTable";
import ReachMap from "./ReachMap";
import { predictionImageUrl } from "../../api/pipeline";

interface ResultsDashboardProps {
  result: AnalysisResult;
  imageUrl: string;
  fileName: string;
}

export default function ResultsDashboard({ result, imageUrl, fileName }: ResultsDashboardProps) {
  const job = result.job;
  const [selected, setSelected] = useState<ReachFeature | null>(null);
  const onSelect = useCallback((feature: ReachFeature) => {
    setSelected(feature);
  }, []);
  const source = job?.label_source || job?.geojson?.metadata?.label_source || "model";
  const mode = job?.pipeline_mode || job?.geojson?.metadata?.pipeline_mode || "ortho_only";
  const modelVersion = job?.model_version || job?.geojson?.metadata?.model_version || "unknown";
  const predId = job?.prediction_id || "";

  const sourceLabel =
    source === "field_verified"
      ? "Field-verified labels (not used in Phase 1 runtime)"
      : source === "rule"
        ? "Rule / alignment-assisted result — not field verified"
        : "Model prediction — not field verified";

  const inspect = selected?.properties;
  const thumb =
    predId && inspect?.thumbnail_relpath ? predictionImageUrl(predId, inspect.thumbnail_relpath) : "";

  const summaryCards = useMemo(() => {
    const s = job?.summary;
    if (!s) return [];
    return [
      ["Reaches", s.total_reaches],
      ["Clear", s.clear],
      ["Partial", s.partial],
      ["Moderate", s.moderate ?? 0],
      ["Full", s.full ?? s.blocked ?? 0],
    ];
  }, [job]);

  return (
    <div className="animate-fade-up">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-canal-500">Analysis Complete</p>
          <h3 className="font-display text-2xl font-semibold text-canal-950">Survey Result</h3>
        </div>
        <StatusBadge detected={result.blockageDetected} />
      </div>

      <div className="mb-5 rounded-lg border border-teal-200 bg-teal-50 px-4 py-3 text-sm text-canal-800">
        <p className="font-semibold">{sourceLabel}</p>
        <p className="mt-1 font-mono text-xs text-canal-600">
          pipeline_mode={mode} · model_version={modelVersion}
        </p>
      </div>

      {job && (
        <div className="mb-5">
          <ReachMap job={job} selectedId={selected?.properties.reach_id} onSelect={onSelect} />
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_1.3fr]">
        <div className="reticle overflow-hidden rounded-xl border border-canal-100 shadow-sm">
          {thumb ? (
            <img src={thumb} alt="Reach thumbnail" className="max-h-[420px] w-full object-cover" />
          ) : imageUrl ? (
            <img src={imageUrl} alt="Analyzed drone survey" className="max-h-[420px] w-full object-cover" />
          ) : (
            <div className="flex max-h-[420px] min-h-[220px] items-center justify-center bg-canal-950 px-6 py-16 text-sm text-teal-200">
              Click a reach on the map to inspect its thumbnail
            </div>
          )}
          <div className="flex items-center justify-between bg-canal-950 px-4 py-2.5 font-mono text-xs text-teal-300">
            <span className="flex items-center gap-1.5">
              <ScanEye className="h-3.5 w-3.5" />
              {inspect ? `Reach ${inspect.reach_id}` : fileName}
            </span>
            <span>{result.imageId}</span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-5">
          {inspect ? (
            <>
              <InfoCard label="Blockage status" className="col-span-2 sm:col-span-1">
                <p className="font-display text-2xl font-semibold capitalize text-canal-950">
                  {inspect.blockage_status || inspect.status}
                </p>
              </InfoCard>
              <InfoCard label="Blockage %" icon={<Percent className="h-4 w-4" />} className="col-span-2 sm:col-span-1">
                <p className="font-mono text-2xl font-semibold text-canal-950">
                  {inspect.blockage_pct ?? inspect.blockage_percentage ?? 0}
                </p>
              </InfoCard>
              <InfoCard label="Structural damage" className="col-span-2 sm:col-span-1">
                <p className="font-display text-2xl font-semibold text-canal-950">
                  {inspect.structural_damage || inspect.damage ? "Yes" : "No"}
                </p>
              </InfoCard>
              <InfoCard label="Model / mode" className="col-span-2 sm:col-span-1">
                <p className="font-mono text-sm text-canal-800">{modelVersion}</p>
                <p className="mt-1 text-sm text-canal-600">{mode}</p>
              </InfoCard>
            </>
          ) : (
            <>
              <InfoCard label="Confidence" icon={<Gauge className="h-4 w-4" />} className="col-span-2 sm:col-span-1">
                <ConfidenceGauge confidence={result.confidence} />
              </InfoCard>
              <InfoCard label="Severity" icon={<LayoutGrid className="h-4 w-4" />} className="col-span-2 sm:col-span-1">
                <SeverityMeter severity={result.severity} />
              </InfoCard>
            </>
          )}
        </div>
      </div>

      {summaryCards.length > 0 && (
        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-5">
          {summaryCards.map(([label, value]) => (
            <div key={String(label)} className="rounded-lg border border-canal-100 bg-white px-4 py-3">
              <p className="text-xs uppercase tracking-wider text-canal-500">{label}</p>
              <p className="mt-1 font-mono text-xl font-semibold text-canal-950">{value}</p>
            </div>
          ))}
        </div>
      )}

      {job && <ReachTable job={job} selectedId={selected?.properties.reach_id} onSelect={onSelect} />}

      <div className="mt-5">
        <RecommendationsList items={result.recommendations} />
      </div>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-canal-100 bg-canal-50 p-5">
        <p className="text-sm text-canal-600">
          Report generated {new Date(result.analyzedAt).toLocaleString()}. This is an automated prediction,
          not a field-verified survey.
        </p>
        <button
          onClick={() => downloadReport(result, fileName)}
          className="inline-flex items-center gap-2 rounded-md bg-canal-800 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-canal-700"
        >
          <Download className="h-4 w-4" />
          Download Report
        </button>
      </div>
    </div>
  );
}
