import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { JobResult, ReachFeature } from "../../types";
import { orthoPreviewUrl } from "../../api/pipeline";

const COLORS: Record<string, string> = {
  clear: "#16a34a",
  partial: "#d68c22",
  moderate: "#ea580c",
  full: "#dc2626",
};

interface Props {
  job: JobResult;
  onSelect: (feature: ReachFeature) => void;
  selectedId?: string;
}

/** Ortho bounds as [[south, west], [north, east]] if the backend supplies them. */
function orthoBounds(job: JobResult): L.LatLngBoundsExpression | null {
  const meta = job.geojson?.metadata;
  const b = meta?.ortho_bounds;
  if (
    b &&
    Array.isArray(b) &&
    b.length === 2 &&
    Array.isArray(b[0]) &&
    Array.isArray(b[1]) &&
    b[0].length === 2 &&
    b[1].length === 2
  ) {
    const south = Number(b[0][0]);
    const west = Number(b[0][1]);
    const north = Number(b[1][0]);
    const east = Number(b[1][1]);
    if ([south, west, north, east].every((n) => Number.isFinite(n))) {
      return [
        [south, west],
        [north, east],
      ];
    }
  }
  return null;
}

export default function ReachMap({ job, onSelect, selectedId }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const orthoRef = useRef<L.ImageOverlay | null>(null);
  const bounds = orthoBounds(job);
  const hasOrtho =
    Boolean(job.outputs?.ortho_preview) && Boolean(bounds) && Boolean(job.prediction_id);
  const [showOrtho, setShowOrtho] = useState(hasOrtho);

  useEffect(() => {
    setShowOrtho(hasOrtho);
  }, [hasOrtho]);

  useEffect(() => {
    if (!ref.current) return;
    const map = L.map(ref.current, { zoomControl: true }).setView([16.2, 77.11], 13);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap",
    }).addTo(map);

    const overlayBounds = orthoBounds(job);
    const canOrtho =
      Boolean(job.outputs?.ortho_preview) && Boolean(overlayBounds) && Boolean(job.prediction_id);

    if (canOrtho && overlayBounds && job.prediction_id) {
      const overlay = L.imageOverlay(orthoPreviewUrl(job.prediction_id), overlayBounds, { opacity: 1 });
      overlay.addTo(map);
      orthoRef.current = overlay;
    }

    const layer = L.geoJSON(job.geojson as never, {
      style: (feat) => {
        const props = (feat?.properties || {}) as ReachFeature["properties"];
        const st = props.blockage_status || props.status || "clear";
        const id = String(props.reach_id ?? "");
        return {
          color: COLORS[st] || "#64748b",
          weight: id === selectedId ? 4 : 2,
          fillOpacity: 0.35,
        };
      },
      onEachFeature: (feat, lyr) => {
        const props = feat.properties as ReachFeature["properties"];
        lyr.on("click", () =>
          onSelect({
            type: "Feature",
            geometry: (feat.geometry || null) as unknown as Record<string, unknown> | null,
            properties: props,
          })
        );
      },
    }).addTo(map);

    try {
      if (canOrtho && overlayBounds) {
        map.fitBounds(overlayBounds, { padding: [24, 24] });
      } else {
        const b = layer.getBounds();
        if (b.isValid()) map.fitBounds(b.pad(0.15));
      }
    } catch {
      /* empty */
    }

    return () => {
      map.remove();
      orthoRef.current = null;
    };
  }, [job, onSelect, selectedId]);

  useEffect(() => {
    if (orthoRef.current) orthoRef.current.setOpacity(showOrtho ? 1 : 0);
  }, [showOrtho]);

  return (
    <div className="relative">
      {hasOrtho && (
        <div className="absolute right-3 top-3 z-[500] inline-flex rounded-lg border border-canal-100 bg-white/90 p-1 shadow-sm backdrop-blur">
          <button
            onClick={() => setShowOrtho(true)}
            className={`rounded-md px-3 py-1 text-xs font-semibold transition ${
              showOrtho ? "bg-canal-800 text-white" : "text-canal-600 hover:text-teal-600"
            }`}
          >
            Drone ortho
          </button>
          <button
            onClick={() => setShowOrtho(false)}
            className={`rounded-md px-3 py-1 text-xs font-semibold transition ${
              !showOrtho ? "bg-canal-800 text-white" : "text-canal-600 hover:text-teal-600"
            }`}
          >
            Base map
          </button>
        </div>
      )}
      <div ref={ref} className="h-[440px] w-full overflow-hidden rounded-xl border border-canal-100" />
    </div>
  );
}
