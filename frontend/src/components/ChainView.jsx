import { useEffect, useState } from 'react'
import { getBoxes, overviewUrl } from '../lib/api.js'

const HEX = { clear: '#10b981', partial: '#f59e0b', moderate: '#f97316', blocked: '#ef4444' }

export default function ChainView({ jobId, selectedId, onSelect }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')
  useEffect(() => { getBoxes(jobId).then(setData).catch(() => setErr('Chain view unavailable.')) }, [jobId])

  if (err) return <div className="text-sm text-slate-400 p-6 text-center">{err}</div>
  if (!data) return <div className="text-sm text-slate-400 p-6 text-center">Loading chain…</div>

  const { width, height, boxes } = data
  return (
    <div>
      <div className="relative mx-auto max-h-[620px] overflow-auto rounded-xl border border-slate-800 bg-slate-900"
           style={{ maxWidth: '100%' }}>
        <div className="relative" style={{ width: '100%', aspectRatio: `${width} / ${height}` }}>
          <img src={overviewUrl(jobId)} alt="Canal chain overview"
               className="absolute inset-0 w-full h-full object-contain select-none" draggable="false" />
          <svg viewBox={`0 0 ${width} ${height}`} className="absolute inset-0 w-full h-full" preserveAspectRatio="xMidYMid meet">
            {boxes.map(b => {
              const sel = b.id === selectedId
              return (
                <rect key={b.id} x={b.x} y={b.y} width={b.w} height={b.h}
                      rx="2"
                      fill={sel ? HEX[b.status] + '55' : 'transparent'}
                      stroke={sel ? '#ffffff' : HEX[b.status] || '#cbd5e1'}
                      strokeWidth={sel ? 4 : 2}
                      style={{ cursor: 'pointer' }}
                      onClick={() => onSelect && onSelect(b)}>
                  <title>{`Reach ${b.id} · ${b.status} · ${b.chainage} m`}</title>
                </rect>
              )
            })}
          </svg>
        </div>
      </div>
      <p className="mt-2 text-xs text-slate-400 text-center">
        {boxes.length} reaches along the canal. Click any segment to open its imagery and coordinates.
      </p>
    </div>
  )
}
