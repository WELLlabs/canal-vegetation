import { ArrowDown, ShieldCheck, Satellite, Timer } from "lucide-react";
import ContourBackground from "./ContourBackground";

export default function Hero() {
  return (
    <section className="relative overflow-hidden bg-canal-950 text-white">
      <ContourBackground variant="dark" />
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-canal-950/0 via-canal-950/40 to-canal-950" />

      {/* signature: slow scan sweep, ambient in the hero, literal during analysis later */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-full overflow-hidden opacity-30">
        <div className="animate-scan absolute inset-x-0 h-24 bg-gradient-to-b from-transparent via-teal-400/70 to-transparent" />
      </div>

      <div className="relative mx-auto max-w-6xl px-6 py-24 md:py-32">
        <div className="max-w-2xl animate-fade-up">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs font-medium uppercase tracking-[0.14em] text-teal-300">
            <Satellite className="h-3.5 w-3.5" />
            Aerial Survey Intelligence
          </div>

          <h1 className="font-display text-4xl font-semibold leading-[1.08] tracking-tight md:text-6xl">
            See what's blocking
            <br />
            the flow, before it floods.
          </h1>

          <p className="mt-6 max-w-lg text-lg text-canal-100/80">
            Upload a GeoTIFF orthomosaic, optionally with a canal alignment. The app runs the
            reference UNet canal pipeline asynchronously and shows predicted reaches on a map.
            Results are model or alignment-assisted — not field verified.
          </p>

          <div className="mt-9 flex flex-wrap items-center gap-4">
            <a
              href="#upload"
              className="inline-flex items-center gap-2 rounded-md bg-teal-500 px-6 py-3 text-sm font-semibold text-canal-950 transition hover:bg-teal-400"
            >
              Analyze an Orthomosaic
              <ArrowDown className="h-4 w-4" />
            </a>
            <a
              href="#how-it-works"
              className="inline-flex items-center gap-2 rounded-md border border-white/20 px-6 py-3 text-sm font-medium text-white/90 transition hover:border-white/40 hover:bg-white/5"
            >
              How the model works
            </a>
          </div>

          <dl className="mt-14 grid max-w-lg grid-cols-3 gap-6 border-t border-white/10 pt-8 font-mono">
            <div>
              <dt className="text-[11px] uppercase tracking-wider text-canal-100/50">Canal model</dt>
              <dd className="mt-1 text-xl font-semibold text-teal-300">UNet</dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-wider text-canal-100/50">Runtime modes</dt>
              <dd className="mt-1 text-xl font-semibold text-teal-300">2</dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-wider text-canal-100/50">Field verified</dt>
              <dd className="mt-1 text-xl font-semibold text-teal-300">No</dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="relative mx-auto max-w-6xl px-6 pb-10">
        <div className="grid grid-cols-1 gap-3 border-t border-white/10 pt-6 text-xs text-canal-100/60 sm:grid-cols-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-teal-400" />
            Built for irrigation & flood-control field teams
          </div>
          <div className="flex items-center gap-2">
            <Satellite className="h-4 w-4 text-teal-400" />
            Optimized for standard drone RGB imagery
          </div>
          <div className="flex items-center gap-2">
            <Timer className="h-4 w-4 text-teal-400" />
            Results after tiled inference, not a site visit
          </div>
        </div>
      </div>
    </section>
  );
}
