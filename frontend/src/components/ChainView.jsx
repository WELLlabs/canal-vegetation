import { useEffect, useRef, useState, useCallback } from 'react'
import { getBoxes, overviewUrl } from '../lib/api.js'

const HEX = { clear: '#10b981', partial: '#f59e0b', moderate: '#f97316', blocked: '#ef4444', no_canal: '#94a3b8' }
const MIN_Z = 1, MAX_Z = 12

function boxRect(b) {
  if (b.w != null && b.h != null) return { x: b.x, y: b.y, w: b.w, h: b.h }
  const line = b.line
  if (!line?.length) return null
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
  for (const [x, y] of line) {
    if (x < minX) minX = x
    if (y < minY) minY = y
    if (x > maxX) maxX = x
    if (y > maxY) maxY = y
  }
  return { x: minX, y: minY, w: Math.max(3, maxX - minX), h: Math.max(3, maxY - minY) }
}

function ZoomButton({ onClick, title, children, disabled }) {
  return (
    <button type="button" onClick={onClick} title={title} aria-label={title} disabled={disabled}
      className="h-8 w-8 grid place-items-center rounded-lg bg-white/95 text-slate-700 shadow border border-slate-200 hover:text-brand-700 disabled:opacity-40">
      {children}
    </button>
  )
}

export default function ChainView({ jobId, selectedId, onSelect }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')
  const [zoom, setZoom] = useState(1)
  const box = useRef(null)
  const drag = useRef(null)
  const zoomRef = useRef(1)
  zoomRef.current = zoom
  useEffect(() => { getBoxes(jobId).then(setData).catch(() => setErr('Chain view unavailable.')) }, [jobId])

  // Zoom about a point of the viewport (cx, cy in px), keeping that image point under it.
  const zoomTo = useCallback((next, cx, cy) => {
    const el = box.current
    if (!el) return
    setZoom(z => {
      const nz = Math.min(MAX_Z, Math.max(MIN_Z, next(z)))
      if (nz === z) return z
      const px = cx ?? el.clientWidth / 2, py = cy ?? el.clientHeight / 2
      const ix = (el.scrollLeft + px) / z, iy = (el.scrollTop + py) / z
      requestAnimationFrame(() => {
        el.scrollLeft = ix * nz - px
        el.scrollTop = iy * nz - py
      })
      return nz
    })
  }, [])

  // Wheel / trackpad pinch zoom (non-passive so the page does not scroll instead).
  useEffect(() => {
    const el = box.current
    if (!el) return
    const onWheel = (e) => {
      // At full view, a plain scroll down still scrolls the page; zoom needs scroll up or a pinch.
      if (zoomRef.current <= MIN_Z && e.deltaY > 0 && !e.ctrlKey) return
      e.preventDefault()
      const r = el.getBoundingClientRect()
      const f = Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.002))
      zoomTo(z => z * f, e.clientX - r.left, e.clientY - r.top)
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [zoomTo, data])

  // Drag to pan (a click without movement still selects a reach).
  const onPointerDown = (e) => {
    if (e.button !== 0 || zoom === 1) return
    const el = box.current
    drag.current = { x: e.clientX, y: e.clientY, sl: el.scrollLeft, st: el.scrollTop, moved: false }
  }
  const onPointerMove = (e) => {
    const d = drag.current
    if (!d) return
    const dx = e.clientX - d.x, dy = e.clientY - d.y
    if (Math.abs(dx) + Math.abs(dy) > 3) d.moved = true
    box.current.scrollLeft = d.sl - dx
    box.current.scrollTop = d.st - dy
  }
  const endDrag = () => { setTimeout(() => { drag.current = null }, 0) }
  const pick = (b) => { if (drag.current?.moved) return; onSelect && onSelect(b) }

  if (err) return <div className="text-sm text-slate-400 p-6 text-center">{err}</div>
  if (!data) return <div className="text-sm text-slate-400 p-6 text-center">Loading chain…</div>

  const { width, height, boxes } = data
  const fs = Math.max(10, width / 260)          // label size in image px at zoom 1
  const nCheck = boxes.filter(b => b.line_check).length
  return (
    <div>
      <div className="relative">
        <div className="absolute right-3 top-3 z-10 flex flex-col gap-1.5">
          <ZoomButton title="Zoom in" onClick={() => zoomTo(z => z * 1.5)} disabled={zoom >= MAX_Z}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 5v14M5 12h14" /></svg>
          </ZoomButton>
          <ZoomButton title="Zoom out" onClick={() => zoomTo(z => z / 1.5)} disabled={zoom <= MIN_Z}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14" /></svg>
          </ZoomButton>
          <ZoomButton title="Fit whole image" onClick={() => zoomTo(() => 1)} disabled={zoom === 1}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" /></svg>
          </ZoomButton>
          <span className="mt-1 rounded-md bg-slate-900/70 px-1.5 py-0.5 text-center text-[11px] font-medium text-white tabular-nums">{Math.round(zoom * 100)}%</span>
        </div>
        <div ref={box}
             className={`relative mx-auto max-h-[620px] overflow-auto rounded-xl border border-slate-800 bg-slate-900 ${zoom > 1 ? 'cursor-grab active:cursor-grabbing' : ''}`}
             onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={endDrag} onPointerLeave={endDrag}>
          <div className="relative" style={{ width: `${zoom * 100}%`, aspectRatio: `${width} / ${height}` }}>
            <img src={overviewUrl(jobId)} alt="Canal chain overview"
                 className="absolute inset-0 w-full h-full object-contain select-none pointer-events-none" draggable="false" />
            <svg viewBox={`0 0 ${width} ${height}`} className="absolute inset-0 w-full h-full" preserveAspectRatio="xMidYMid meet">
              {boxes.map(b => {
                const r = boxRect(b)
                if (!r) return null
                const sel = b.id === selectedId
                const c = HEX[b.status] || '#cbd5e1'
                return (
                  <g key={b.id} style={{ cursor: 'pointer' }} onClick={() => pick(b)}>
                    <rect x={r.x} y={r.y} width={r.w} height={r.h} rx="2"
                          fill={sel ? c + '55' : 'transparent'}
                          stroke={sel ? '#ffffff' : c}
                          strokeWidth={sel ? 3.5 : 2}
                          strokeDasharray={b.line_check ? '5 3' : undefined}
                          vectorEffect="non-scaling-stroke" />
                    {zoom >= 2 && (
                      <text x={r.x} y={r.y - fs * 0.3 / zoom} fontSize={fs * 1.4 / zoom} fill="#fff"
                            stroke="#000" strokeWidth={fs * 0.25 / zoom} paintOrder="stroke"
                            style={{ pointerEvents: 'none' }}>
                        {b.id}{b.blockpct != null ? ` · ${b.blockpct}%` : ''}
                      </text>
                    )}
                    <title>{`Reach ${b.id} · ${b.status} · ${b.blockpct ?? '–'}% vegetation · ${b.chainage} m${b.line_check ? ' · weak canal signal, check' : ''}`}</title>
                  </g>
                )
              })}
            </svg>
          </div>
        </div>
      </div>
      <p className="mt-2 text-xs text-slate-400 text-center">
        {boxes.length} reaches along the canal{nCheck ? ` (${nCheck} dashed: weak canal signal, worth a look)` : ''}.
        Scroll or use + / − to zoom, drag to pan, click any box for its imagery and GeoJSON.
      </p>
    </div>
  )
}
