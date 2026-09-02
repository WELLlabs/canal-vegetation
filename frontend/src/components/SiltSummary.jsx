// Shown only when DSM + DTM were uploaded and silt was computed.
const SILT = {
  low:    { label: 'Low',    hint: '< 0.5 m', bg: 'bg-sky-400' },
  medium: { label: 'Medium', hint: '0.5-1 m', bg: 'bg-indigo-400' },
  high:   { label: 'High',   hint: '> 1 m',   bg: 'bg-violet-600' },
}
const inr = (n) => Number(n || 0).toLocaleString('en-IN')

export default function SiltSummary({ silt }) {
  if (!silt || !silt.reaches) return null
  const dist = silt.distribution || {}
  const max = Math.max(1, ...Object.values(dist))
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-slate-900">Silt estimate</h2>
        <span className="text-xs text-slate-500">from DSM - DTM</span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3">
        <div className="rounded-xl bg-slate-50 border border-slate-100 p-3">
          <div className="text-2xl font-bold tabular-nums text-slate-900">{inr(silt.total_volume_m3)}</div>
          <div className="text-xs text-slate-500">estimated silt, m&sup3;</div>
        </div>
        <div className="rounded-xl bg-slate-50 border border-slate-100 p-3">
          <div className="text-2xl font-bold tabular-nums text-slate-900">{silt.mean_depth_m} m</div>
          <div className="text-xs text-slate-500">mean depth over {silt.reaches} reaches</div>
        </div>
      </div>

      <div className="mt-4 space-y-3">
        {Object.entries(SILT).map(([k, s]) => {
          const n = dist[k] || 0
          const pct = silt.reaches ? Math.round(100 * n / silt.reaches) : 0
          return (
            <div key={k} className="flex items-center gap-3">
              <div className="w-24 text-sm font-medium text-slate-700">{s.label}<span className="text-slate-400 font-normal"> {s.hint}</span></div>
              <div className="flex-1 h-3 rounded-full bg-slate-100 overflow-hidden">
                <div className={`h-full ${s.bg} rounded-full`} style={{ width: `${(n/max)*100}%` }} />
              </div>
              <div className="w-16 text-right text-sm tabular-nums text-slate-600">{n} · {pct}%</div>
            </div>
          )
        })}
      </div>

      <p className="mt-4 text-xs text-slate-400">
        Silt is estimated as canal-surface minus terrain elevation (DSM - DTM). Dense vegetation above the channel can raise this, so treat figures as indicative, not survey-grade.
      </p>
    </div>
  )
}
