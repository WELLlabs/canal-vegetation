import { predictionImageUrl } from "../../api/pipeline";
import type { JobResult, ReachFeature } from "../../types";

function statusOf(p: ReachFeature["properties"]) {
  return p.blockage_status || p.status || "clear";
}

function pctOf(p: ReachFeature["properties"]) {
  return p.blockage_pct ?? p.blockage_percentage ?? 0;
}

export default function ReachTable({
  job,
  selectedId,
  onSelect,
}: {
  job: JobResult;
  selectedId?: string;
  onSelect: (f: ReachFeature) => void;
}) {
  const features = job.features?.length ? job.features : job.geojson?.features || [];
  if (!features.length) return null;
  const predId = job.prediction_id || "";

  const rows = [...features].sort(
    (a, b) => (a.properties.chainage_m ?? a.properties.chainage ?? 0) - (b.properties.chainage_m ?? b.properties.chainage ?? 0)
  );

  return (
    <div className="mt-5 overflow-hidden rounded-xl border border-canal-100 bg-white">
      <div className="border-b border-canal-100 px-5 py-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-canal-500">Per-reach results</p>
        <p className="mt-0.5 text-sm text-canal-600">{rows.length} reaches — click a row or map polygon to inspect</p>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-canal-50 font-mono text-xs uppercase tracking-wide text-canal-500">
            <tr>
              <th className="px-4 py-2">Reach</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">Blockage %</th>
              <th className="px-4 py-2">Damage</th>
              <th className="px-4 py-2">Chainage</th>
              <th className="px-4 py-2">Preview</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((f) => {
              const p = f.properties;
              const rel = p.thumbnail_relpath || "";
              const thumb = predId && rel ? predictionImageUrl(predId, rel) : "";
              const selected = String(p.reach_id) === selectedId;
              return (
                <tr
                  key={p.reach_id}
                  className={`cursor-pointer border-t border-canal-100 ${selected ? "bg-teal-50" : "hover:bg-canal-50"}`}
                  onClick={() => onSelect(f)}
                >
                  <td className="px-4 py-2 font-mono text-canal-800">{p.reach_id}</td>
                  <td className="px-4 py-2 capitalize">{statusOf(p)}</td>
                  <td className="px-4 py-2 font-mono">{pctOf(p)}</td>
                  <td className="px-4 py-2">{p.structural_damage || p.damage ? "Yes" : "No"}</td>
                  <td className="px-4 py-2 font-mono">{(p.chainage_m ?? p.chainage ?? 0).toFixed(0)} m</td>
                  <td className="px-4 py-2">
                    {thumb ? <img src={thumb} alt={p.reach_id} className="h-12 w-16 rounded object-cover" /> : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
