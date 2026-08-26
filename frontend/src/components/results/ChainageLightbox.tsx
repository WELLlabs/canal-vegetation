import { useCallback, useEffect, useRef } from "react";
import { X, ChevronLeft, ChevronRight, AlertTriangle, MapPin } from "lucide-react";
import type { ReachFeature } from "../../types";
import { predictionImageUrl } from "../../api/pipeline";
import ChannelSection from "./ChannelSection";

const SEV: Record<string, { hex: string; label: string; range: string }> = {
  clear: { hex: "#16a34a", label: "Clear", range: "0–5%" },
  partial: { hex: "#d68c22", label: "Partial", range: "6–39%" },
  moderate: { hex: "#ea580c", label: "Moderate", range: "40–70%" },
  full: { hex: "#dc2626", label: "Full", range: "71–100%" },
};

const statusOf = (p: ReachFeature["properties"]) => p.blockage_status || p.status || "clear";
const pctOf = (p: ReachFeature["properties"]) => p.blockage_pct ?? p.blockage_percentage ?? 0;
const chOf = (p: ReachFeature["properties"]) => p.chainage_m ?? p.chainage ?? 0;
const dmgOf = (p: ReachFeature["properties"]) => Boolean(p.structural_damage || p.damage);

export default function ChainageLightbox({
  features,
  index,
  predId,
  onClose,
  onNavigate,
}: {
  features: ReachFeature[];
  index: number;
  predId: string;
  onClose: () => void;
  onNavigate: (i: number) => void;
}) {
  const f = features[index];
  const stripRef = useRef<HTMLDivElement>(null);

  const go = useCallback(
    (d: number) => onNavigate((index + d + features.length) % features.length),
    [index, features.length, onNavigate]
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowRight") go(1);
      else if (e.key === "ArrowLeft") go(-1);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [go, onClose]);

  useEffect(() => {
    const el = stripRef.current?.querySelector<HTMLElement>(`[data-i="${index}"]`);
    el?.scrollIntoView({ inline: "center", block: "nearest" });
  }, [index]);

  if (!f) return null;
  const p = f.properties;
  const st = statusOf(p);
  const sev = SEV[st] ?? { hex: "#64748b", label: st, range: "" };
  const pct = pctOf(p);
  const dmg = dmgOf(p);
  const image = predId && p.thumbnail_relpath ? predictionImageUrl(predId, p.thumbnail_relpath) : "";

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col bg-canal-950/85 p-4 backdrop-blur-md sm:p-8 animate-fade-up"
      role="dialog"
      aria-modal="true"
      aria-label="Chainage inspection"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="mb-4 flex items-center gap-4 text-white">
        <div>
          <h2 className="font-display text-lg font-bold">
            {p.canal_name || "Canal"} · {chOf(p).toLocaleString()} m
          </h2>
          <p className="text-xs text-canal-100/70">
            Reach {index + 1} of {features.length} · #{p.reach_id}
          </p>
        </div>
        <button
          onClick={onClose}
          className="ml-auto grid h-9 w-9 place-items-center rounded-lg border border-white/15 bg-white/5 text-white transition hover:border-teal-400 hover:text-teal-400"
          aria-label="Close"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="relative grid min-h-0 flex-1 gap-4 lg:grid-cols-[1.3fr_0.9fr]">
        <button
          onClick={() => go(-1)}
          className="absolute left-1 top-1/2 z-10 grid h-11 w-11 -translate-y-1/2 place-items-center rounded-full border border-white/15 bg-canal-900/80 text-white transition hover:border-teal-400 hover:text-teal-400"
          aria-label="Previous chainage"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
        <button
          onClick={() => go(1)}
          className="absolute right-1 top-1/2 z-10 grid h-11 w-11 -translate-y-1/2 place-items-center rounded-full border border-white/15 bg-canal-900/80 text-white transition hover:border-teal-400 hover:text-teal-400"
          aria-label="Next chainage"
        >
          <ChevronRight className="h-5 w-5" />
        </button>

        <div className="flex min-h-0 flex-col gap-4">
          <div className="reticle flex-1 overflow-hidden rounded-2xl border border-white/10 bg-black">
            {image ? (
              <img src={image} alt={`Reach ${p.reach_id}`} className="h-full w-full object-cover" />
            ) : (
              <ChannelSection status={st} pct={pct} damage={dmg} />
            )}
          </div>
          <div className="h-40 shrink-0 overflow-hidden rounded-2xl border border-white/10 bg-canal-900">
            <div className="flex items-center justify-between border-b border-white/10 px-4 py-2 font-mono text-[11px] uppercase tracking-wider text-canal-100/60">
              <span>Channel cross-section · plan view</span>
              <span>CH {chOf(p)} m</span>
            </div>
            <div className="h-[calc(100%-33px)]">
              <ChannelSection status={st} pct={pct} damage={dmg} />
            </div>
          </div>
        </div>

        <div className="flex min-h-0 flex-col gap-3 overflow-y-auto">
          <span
            className="inline-flex items-center gap-2 self-start rounded-full px-4 py-1.5 text-sm font-bold text-white"
            style={{ background: sev.hex }}
          >
            <span className="h-2 w-2 rounded-full bg-white" />
            {sev.label} blockage
          </span>

          <div className="rounded-xl border border-white/10 bg-canal-900 p-4">
            <p className="text-[11px] uppercase tracking-wider text-canal-100/60">Verified blockage</p>
            <div className="mt-2 flex items-center gap-4">
              <div className="font-display text-4xl font-extrabold leading-none text-white">
                {pct}
                <span className="text-lg text-canal-100/60">%</span>
              </div>
              <div className="flex-1">
                <div className="h-3 overflow-hidden rounded-full border border-white/10 bg-white/5">
                  <div className="h-full rounded-full" style={{ width: `${pct}%`, background: sev.hex }} />
                </div>
                <p className="mt-1.5 font-mono text-[11px] text-canal-100/50">class range {sev.range}</p>
              </div>
            </div>
          </div>

          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 rounded-xl border border-white/10 bg-canal-900 p-4 text-sm text-white">
            <dt className="text-canal-100/60">Chainage</dt>
            <dd className="text-right font-mono">{chOf(p).toLocaleString()} m</dd>
            <dt className="text-canal-100/60">Canal</dt>
            <dd className="text-right">{p.canal_name || "—"}</dd>
            <dt className="text-canal-100/60">Type</dt>
            <dd className="text-right capitalize">{p.canal_type || "—"}</dd>
            <dt className="text-canal-100/60">Reach ID</dt>
            <dd className="text-right font-mono">#{p.reach_id}</dd>
            <dt className="text-canal-100/60">Latitude</dt>
            <dd className="text-right font-mono">{p.centroid_lat?.toFixed(6) ?? "—"}</dd>
            <dt className="text-canal-100/60">Longitude</dt>
            <dd className="text-right font-mono">{p.centroid_lon?.toFixed(6) ?? "—"}</dd>
            <dt className="text-canal-100/60">Structural</dt>
            <dd className="text-right">
              {dmg ? (
                <span className="inline-flex items-center gap-1 font-semibold text-danger-500">
                  <AlertTriangle className="h-3.5 w-3.5" /> Damage flagged
                </span>
              ) : (
                <span className="text-success-500">None</span>
              )}
            </dd>
          </dl>

          {(p.centroid_lat != null || image) && (
            <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-canal-900 p-3 text-xs text-canal-100/70">
              <MapPin className="h-3.5 w-3.5 shrink-0 text-teal-400" />
              <span>
                Close-up frame{" "}
                <span className="font-mono">{p.thumbnail_relpath?.split("/").pop() || "—"}</span>
              </span>
            </div>
          )}
        </div>
      </div>

      <div ref={stripRef} className="mt-4 flex shrink-0 gap-1 overflow-x-auto pb-1">
        {features.map((feat, i) => {
          const fp = feat.properties;
          const s = statusOf(fp);
          const sv = SEV[s] ?? { hex: "#64748b" };
          const fpct = pctOf(fp);
          return (
            <button
              key={fp.reach_id}
              data-i={i}
              onClick={() => onNavigate(i)}
              title={`${fp.canal_name || ""} ${chOf(fp)}m · ${s} ${fpct}%`}
              className={`relative flex h-11 w-6 shrink-0 items-end justify-center overflow-hidden rounded-md border transition ${
                i === index ? "border-teal-400 outline outline-2 outline-teal-400" : "border-black/20"
              }`}
              style={{ background: `${sv.hex}26` }}
            >
              <span className="w-full" style={{ height: `${Math.max(6, fpct)}%`, background: sv.hex }} />
              {dmgOf(fp) && <span className="absolute right-0.5 top-0.5 h-1 w-1 rounded-full bg-white ring-1 ring-black/40" />}
            </button>
          );
        })}
      </div>
    </div>
  );
}
