import { useEffect, useState } from 'react'
import { getGeojson, reachImageUrl } from '../lib/api.js'
const PILL = {
  clear: 'bg-emerald-100 text-emerald-700', partial: 'bg-amber-100 text-amber-700',
  moderate: 'bg-orange-100 text-orange-700', blocked: 'bg-rose-100 text-rose-700',
  no_canal: 'bg-slate-200 text-slate-700',
}
const LABEL = { no_canal: 'No canal (check)' }
const inr = (n) => Number(n).toLocaleString('en-IN')
function Row({ k, v }) {
  return (<div className="flex justify-between text-sm py-1.5 border-b border-slate-100 last:border-0">
    <span className="text-slate-500">{k}</span><span className="font-medium text-slate-800 tabular-nums">{v}</span></div>)
}

function featureFromReach(reach) {
  const props = {
    id: reach.id, status: reach.status, chainage_m: reach.chainage,
    blockage_pct: reach.blockpct, openpct: reach.openpct, vegpct: reach.vegpct, waterpct: reach.waterpct,
    line_check: reach.line_check || undefined,
    width: reach.width, canal: reach.canal, line_conf: reach.line_conf,
    lat: reach.lat, lon: reach.lon,
    silt_class: reach.silt_class, silt_mean_m: reach.silt_mean_m, silt_vol_m3: reach.silt_vol_m3,
  }
  return {
    type: 'Feature',
    geometry: reach.lon != null && reach.lat != null
      ? { type: 'Point', coordinates: [reach.lon, reach.lat] }
      : null,
    properties: Object.fromEntries(Object.entries(props).filter(([, v]) => v != null)),
  }
}

export default function ReachDetail({ jobId, reach }) {
  const [feature, setFeature] = useState(null)

  useEffect(() => {
    if (!reach) { setFeature(null); return }
    let cancelled = false
    getGeojson(jobId).then(gj => {
      if (cancelled) return
      const f = (gj.features || []).find(x => String(x.properties?.id) === String(reach.id))
      setFeature(f || featureFromReach(reach))
    }).catch(() => { if (!cancelled) setFeature(featureFromReach(reach)) })
    return () => { cancelled = true }
  }, [jobId, reach])

  if (!reach) {
    return <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50/60 p-6 text-sm text-slate-400 h-full grid place-items-center text-center">
      <div>
        <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mx-auto mb-2 text-slate-300"><path d="M21 10c0 7-9 12-9 12s-9-5-9-12a9 9 0 0 1 18 0Z"/><circle cx="12" cy="10" r="3"/></svg>
        Click a reach on the chain or map<br/>to see its imagery and coordinates.
      </div>
    </div>
  }
  const s = reach.status
  const geo = feature || featureFromReach(reach)
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-slate-900">Reach {reach.id}</h3>
        <span className={`text-xs font-semibold rounded-full px-2.5 py-1 capitalize ${PILL[s]||'bg-slate-100 text-slate-600'}`}>{LABEL[s] || s}</span>
      </div>

      {reach.has_image && (
        <img alt={`Reach ${reach.id}`} className="mt-3 w-full rounded-xl border border-slate-200"
             src={reachImageUrl(jobId, reach.id)} />
      )}

      {/* Coordinates, front and centre */}
      <div className="mt-3 rounded-xl bg-brand-50 border border-brand-100 p-3">
        <div className="flex items-center gap-2 text-xs font-semibold text-brand-800 uppercase tracking-wide">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 10c0 7-9 12-9 12s-9-5-9-12a9 9 0 0 1 18 0Z"/><circle cx="12" cy="10" r="3"/></svg>
          Location
        </div>
        <div className="mt-1.5 grid grid-cols-2 gap-2 font-mono text-sm text-slate-800">
          <div><span className="text-slate-400 text-xs">lat </span>{reach.lat}</div>
          <div><span className="text-slate-400 text-xs">lon </span>{reach.lon}</div>
        </div>
      </div>

      <div className="mt-3">
        {reach.blockpct != null && <Row k="Blockage (vegetation cover)" v={`${reach.blockpct} per cent`} />}
        {reach.openpct != null && <Row k="Open channel" v={`${reach.openpct} per cent`} />}
        {reach.waterpct != null && <Row k="Water" v={`${reach.waterpct} per cent`} />}
        {reach.line_conf != null && <Row k="Canal signal (line model)" v={reach.line_conf} />}
        {reach.line_check && <Row k="Check" v="Weak canal signal" />}
        {reach.chainage != null && <Row k="Chainage" v={`${reach.chainage} m`} />}
        {reach.width != null && <Row k="Width" v={`${reach.width} m`} />}
        {reach.silt_class && <Row k="Silt class" v={reach.silt_class} />}
        {reach.silt_mean_m != null && <Row k="Silt depth" v={`${reach.silt_mean_m} m`} />}
        {reach.silt_vol_m3 != null && <Row k="Silt volume" v={`${inr(reach.silt_vol_m3)} m³`} />}
      </div>

      <details className="mt-3 group">
        <summary className="cursor-pointer text-xs font-medium text-slate-500 hover:text-slate-700">GeoJSON</summary>
        <pre className="mt-2 rounded-lg bg-slate-900 text-slate-100 text-[11px] leading-relaxed p-3 overflow-x-auto">{JSON.stringify(geo, null, 2)}</pre>
      </details>
    </div>
  )
}
