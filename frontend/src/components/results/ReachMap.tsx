import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { JobResult, ReachFeature } from "../../types";

const COLORS: Record<string, string> = {
  clear: "#16a34a",
  partial: "#f59e0b",
  moderate: "#ea580c",
  full: "#dc2626",
};

interface Props {
  job: JobResult;
  onSelect: (feature: ReachFeature) => void;
  selectedId?: string;
}

export default function ReachMap({ job, onSelect, selectedId }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const map = L.map(ref.current).setView([16.2, 77.3], 12);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap",
    }).addTo(map);

    const layer = L.geoJSON(job.geojson as never, {
      style: (feat) => {
        const props = (feat?.properties || {}) as ReachFeature["properties"];
        const st = props.blockage_status || "clear";
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
      const b = layer.getBounds();
      if (b.isValid()) map.fitBounds(b.pad(0.15));
    } catch {
      /* empty */
    }

    return () => {
      map.remove();
    };
  }, [job, onSelect, selectedId]);

  return <div ref={ref} className="h-[420px] w-full overflow-hidden rounded-xl border border-canal-100" />;
}
