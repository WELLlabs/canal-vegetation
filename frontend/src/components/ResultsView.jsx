import { useState } from 'react'
import ChainView from './ChainView.jsx'
import MapView from './MapView.jsx'
import ReachModal from './ReachModal.jsx'
import Downloads from './Downloads.jsx'
import ResultSummary from './ResultSummary.jsx'
import SiltSummary from './SiltSummary.jsx'

const inr = (n) => Number(n || 0).toLocaleString('en-IN')

function Tile({ label, value, sub, accent }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className={`text-2xl font-bold tabular-nums ${accent || 'text-slate-900'}`}>{value}</div>
      <div className="text-xs text-slate-500 mt-0.5">{label}</div>
      {sub && <div className="text-[11px] text-slate-400">{sub}</div>}
    </div>
  )
}

const LEGEND = [['Clear', '#10b981'], ['Partial', '#f59e0b'], ['Moderate', '#f97316'], ['Blocked', '#ef4444'], ['Not covered', '#cbd5e1']]

export default function ResultsView({ jobId, summary }) {
  const [tab, setTab] = useState('chain')
  const [sel, setSel] = useState(null)
  const d = summary.distribution || {}
  const covered = summary.covered_reaches || 0
  const blocked = d.blocked || 0
  const attention = (d.blocked || 0) + (d.moderate || 0)
  const silt = summary.silt

  return (
    <div className="rounded-3xl border border-slate-200 bg-gradient-to-b from-white to-slate-50 p-6 shadow-sm">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-widest font-bold text-brand-700">Results</p>
          <h2 className="text-xl font-extrabold text-slate-900">{summary.canal_label}</h2>
        </div>
        <Downloads jobId={jobId} />
      </div>

      {/* Stat tiles */}
      <div className="mt-4 grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Tile label="Reaches scored" value={inr(covered)} sub={`of ${inr(summary.total_reaches)} on this canal`} />
        <Tile label="Blocked" value={inr(blocked)} accent="text-rose-600" sub={`${covered ? Math.round(100 * blocked / covered) : 0}% of scored`} />
        <Tile label="Needs attention" value={inr(attention)} accent="text-orange-600" sub="blocked + moderate" />
        {silt
          ? <Tile label="Silt estimate" value={inr(silt.total_volume_m3)} sub={`m³ · mean ${silt.mean_depth_m} m`} accent="text-indigo-600" />
          : <Tile label="Silt" value="—" sub="add DSM + DTM" />}
      </div>

      {/* Tabs + full-width view; detail opens as a modal */}
      <div className="mt-5">
        <div className="flex items-center justify-between mb-3 flex-wrap gap-3">
          <div className="inline-flex rounded-xl bg-slate-100 p-1">
            {[['chain', 'Chain view'], ['map', 'Map']].map(([k, l]) => (
              <button key={k} onClick={() => setTab(k)}
                className={`px-4 py-1.5 text-sm font-semibold rounded-lg transition ${tab === k ? 'bg-white text-brand-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}>{l}</button>
            ))}
          </div>
          <div className="hidden sm:flex flex-wrap items-center gap-3 text-xs">
            {LEGEND.map(([l, c]) => (<span key={l} className="inline-flex items-center gap-1.5"><span className="h-2.5 w-3.5 rounded-full" style={{ background: c }} />{l}</span>))}
          </div>
        </div>
        {tab === 'chain'
          ? <ChainView jobId={jobId} selectedId={sel?.id} onSelect={setSel} />
          : <MapView key={jobId} jobId={jobId} onSelect={setSel} />}
      </div>

      <div className="mt-5 grid md:grid-cols-2 gap-5">
        <ResultSummary summary={summary} />
        {silt && <SiltSummary silt={silt} />}
      </div>

      <ReachModal jobId={jobId} reach={sel} onClose={() => setSel(null)} />
    </div>
  )
}
