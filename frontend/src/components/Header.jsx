import ModelBadge from './ModelBadge.jsx'

export default function Header({ model }) {
  return (
    <header className="sticky top-0 z-20 bg-white/80 backdrop-blur border-b border-slate-200">
      <div className="mx-auto max-w-6xl px-5 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 grid place-items-center text-white shadow-soft">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M3 7c3 0 3 2 6 2s3-2 6-2 3 2 6 2"/><path d="M3 12c3 0 3 2 6 2s3-2 6-2 3 2 6 2"/><path d="M3 17c3 0 3 2 6 2s3-2 6-2 3 2 6 2"/></svg>
          </div>
          <div className="leading-tight">
            <div className="font-extrabold text-slate-900">Canal Blockage App</div>
            <div className="text-[11px] uppercase tracking-widest text-brand-700 font-semibold">WELL Labs · Canal Intelligence</div>
          </div>
        </div>
        <ModelBadge model={model} compact />
      </div>
    </header>
  )
}
