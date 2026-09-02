export default function CanalPicker({ canals, value, onChange }) {
  return (
    <div className="grid sm:grid-cols-2 gap-3">
      {canals.map(c => {
        const active = value === c.key
        return (
          <button key={c.key} type="button" onClick={() => onChange(c.key)}
            className={`text-left rounded-2xl border p-4 transition
              ${active ? 'border-brand-500 bg-brand-50 ring-2 ring-brand-200' : 'border-slate-200 bg-white hover:border-brand-300'}`}>
            <div className="flex items-center justify-between">
              <div className="font-semibold text-slate-900">{c.label}</div>
              <span className={`h-4 w-4 rounded-full border-2 grid place-items-center ${active?'border-brand-600':'border-slate-300'}`}>
                {active && <span className="h-2 w-2 rounded-full bg-brand-600" />}
              </span>
            </div>
            <div className="mt-1 text-xs text-slate-500">{c.region}</div>
            <div className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-brand-800 bg-white/70 rounded-lg px-2 py-1 border border-brand-100">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 19V5M4 12h16M20 19V5"/></svg>
              {c.reaches != null ? `${c.reaches} reaches ready` : 'alignment bundled'}
            </div>
          </button>
        )
      })}
    </div>
  )
}
