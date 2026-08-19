import { Download, Gauge, LayoutGrid, Percent, ScanEye } from "lucide-react";
import type { AnalysisResult } from "../../types";
import StatusBadge from "./StatusBadge";
import ConfidenceGauge from "./ConfidenceGauge";
import SeverityMeter from "./SeverityMeter";
import InfoCard from "./InfoCard";
import RecommendationsList from "./RecommendationsList";
import { downloadReport } from "../../utils/generateReport";

interface ResultsDashboardProps {
  result: AnalysisResult;
  imageUrl: string;
  fileName: string;
}

export default function ResultsDashboard({ result, imageUrl, fileName }: ResultsDashboardProps) {
  return (
    <div className="animate-fade-up">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-canal-500">Analysis Complete</p>
          <h3 className="font-display text-2xl font-semibold text-canal-950">Survey Result</h3>
        </div>
        <StatusBadge detected={result.blockageDetected} />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_1.3fr]">
        {/* image column */}
        <div className="reticle overflow-hidden rounded-xl border border-canal-100 shadow-sm">
          <img src={imageUrl} alt="Analyzed drone survey" className="max-h-[420px] w-full object-cover" />
          <div className="flex items-center justify-between bg-canal-950 px-4 py-2.5 font-mono text-xs text-teal-300">
            <span className="flex items-center gap-1.5">
              <ScanEye className="h-3.5 w-3.5" />
              {fileName}
            </span>
            <span>{result.imageId}</span>
          </div>
        </div>

        {/* stat grid */}
        <div className="grid grid-cols-2 gap-5">
          <InfoCard label="Confidence" icon={<Gauge className="h-4 w-4" />} className="col-span-2 sm:col-span-1">
            <ConfidenceGauge confidence={result.confidence} />
          </InfoCard>

          <InfoCard label="Severity" icon={<LayoutGrid className="h-4 w-4" />} className="col-span-2 sm:col-span-1">
            <SeverityMeter severity={result.severity} />
          </InfoCard>

          <InfoCard label="Blockage Type" className="col-span-2 sm:col-span-1">
            <p className="font-display text-2xl font-semibold text-canal-950">{result.blockageType}</p>
            <p className="mt-1 text-sm text-canal-600">Primary obstruction classification</p>
          </InfoCard>

          <InfoCard label="Affected Area" icon={<Percent className="h-4 w-4" />} className="col-span-2 sm:col-span-1">
            <p className="font-mono text-2xl font-semibold text-canal-950">
              {result.affectedAreaPercent.toFixed(1)}%
            </p>
            <div className="mt-2.5 h-2 w-full overflow-hidden rounded-full bg-canal-100">
              <div
                className="h-full rounded-full bg-canal-700"
                style={{ width: `${Math.min(100, result.affectedAreaPercent)}%` }}
              />
            </div>
          </InfoCard>
        </div>
      </div>

      <div className="mt-5">
        <RecommendationsList items={result.recommendations} />
      </div>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-canal-100 bg-canal-50 p-5">
        <p className="text-sm text-canal-600">
          Report generated {new Date(result.analyzedAt).toLocaleString()}. Suitable for field records and
          maintenance dispatch.
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
