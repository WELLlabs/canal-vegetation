const STATUS = {
  clear:    { label: 'Clear',    bg: 'bg-emerald-500' },
  partial:  { label: 'Partial',  bg: 'bg-amber-500' },
  moderate: { label: 'Moderate', bg: 'bg-orange-500' },
  blocked:  { label: 'Blocked',  bg: 'bg-rose-500' },
}
export default function ResultSummary({ summary }) {
  if (!summary) return null
  const dist = summary.distribution || {}
  const covered = summary.covered_reaches || 0
  const total = summary.total_reaches || 0

  // No overlap between the orthophoto and the selected canal alignment.
  if (!covered) {
    return (
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5">
        <h2 className="font-semibold text-amber-900">No reaches scored</h2>
        <p className="mt-2 text-sm text-amber-800">
          {summary.message || 'This orthophoto does not overlap the selected canal alignment.'}
        </p>
        <p className="mt-3 text-xs text-amber-700">
          Tip: for the bundled TLBC D95 alignment, the ATTANUR_2, ATTANUR_3, and SHAKAPUR orthophotos overlap the canal; ATTANUR_1 and ATTANUR_4 do not.
        </p>
      </div>
    )
  }

  const max = Math.max(1, ...Object.values(dist))
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-slate-900">Blockage summary</h2>
        <span className="text-xs text-slate-500">{summary.canal_label}</span>
      </div>
      <div className="mt-1 text-sm text-slate-500">
        {covered} of {total} reaches fall inside this orthophoto and were scored.
      </div>
      <div className="mt-4 space-y-3">
        {Object.entries(STATUS).map(([k, s]) => {
          const n = dist[k] || 0
          const pct = covered ? Math.round(100 * n / covered) : 0
          return (
            <div key={k} className="flex items-center gap-3">
              <div className="w-20 text-sm font-medium text-slate-700">{s.label}</div>
              <div className="flex-1 h-3 rounded-full bg-slate-100 overflow-hidden">
                <div className={`h-full ${s.bg} rounded-full`} style={{ width: `${(n/max)*100}%` }} />
              </div>
              <div className="w-16 text-right text-sm tabular-nums text-slate-600">{n} · {pct}%</div>
            </div>
          )
        })}
      </div>
      <p className="mt-4 text-xs text-slate-400">
        Reaches outside the uploaded orthophoto are marked not-covered.
      </p>
    </div>
  )
}
