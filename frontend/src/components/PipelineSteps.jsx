const STEPS = [
  { t: 'Upload', d: 'Orthophoto' },
  { t: 'Reaches', d: '50 m segments' },
  { t: 'Blockage', d: '4-class + %' },
  { t: 'Silt', d: 'Optional' },
  { t: 'Report', d: 'Map & export' },
]
export default function PipelineSteps() {
  return (
    <div className="flex items-center gap-2 overflow-x-auto pb-1">
      {STEPS.map((s, i) => (
        <div key={s.t} className="flex items-center gap-2 shrink-0">
          <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2">
            <span className="h-6 w-6 grid place-items-center rounded-lg bg-brand-50 text-brand-700 text-xs font-bold">{i+1}</span>
            <div className="leading-tight">
              <div className="text-sm font-semibold text-slate-800">{s.t}</div>
              <div className="text-[11px] text-slate-500">{s.d}</div>
            </div>
          </div>
          {i < STEPS.length-1 && <svg width="16" height="16" viewBox="0 0 24 24" className="text-slate-300 shrink-0" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12h14M13 6l6 6-6 6"/></svg>}
        </div>
      ))}
    </div>
  )
}
