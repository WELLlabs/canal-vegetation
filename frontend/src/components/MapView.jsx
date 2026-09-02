import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { getGeojson } from '../lib/api.js'

const COLOR = [
  'match', ['get', 'status'],
  'clear', '#10b981',
  'partial', '#f59e0b',
  'moderate', '#f97316',
  'blocked', '#ef4444',
  '#cbd5e1', // not_covered / default
]
const STYLE = {
  version: 8,
  sources: { osm: { type: 'raster', tileSize: 256,
    tiles: ['https://a.tile.openstreetmap.org/{z}/{x}/{y}.png'],
    attribution: '© OpenStreetMap contributors' } },
  layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
}

export default function MapView({ jobId, onSelect }) {
  const box = useRef(null)
  const map = useRef(null)

  useEffect(() => {
    if (!box.current || map.current) return
    const m = new maplibregl.Map({ container: box.current, style: STYLE,
      center: [77.1, 16.22], zoom: 12 })
    m.addControl(new maplibregl.NavigationControl(), 'top-right')
    map.current = m

    m.on('load', async () => {
      let gj
      try { gj = await getGeojson(jobId) } catch { return }
      m.addSource('reaches', { type: 'geojson', data: gj, promoteId: 'id' })
      m.addLayer({ id: 'reaches-line', type: 'line', source: 'reaches',
        paint: { 'line-color': COLOR,
          'line-width': ['case', ['boolean', ['feature-state', 'sel'], false], 7, 4],
          'line-opacity': 0.9 } })
      // fit to data
      const b = new maplibregl.LngLatBounds()
      gj.features.forEach(f => f.geometry.coordinates.forEach(c => b.extend(c)))
      if (!b.isEmpty()) m.fitBounds(b, { padding: 40, maxZoom: 16 })

      let selId = null
      m.on('click', 'reaches-line', (e) => {
        const f = e.features[0]
        if (selId != null) m.setFeatureState({ source: 'reaches', id: selId }, { sel: false })
        selId = f.id
        m.setFeatureState({ source: 'reaches', id: selId }, { sel: true })
        onSelect && onSelect(f.properties)
      })
      m.on('mouseenter', 'reaches-line', () => m.getCanvas().style.cursor = 'pointer')
      m.on('mouseleave', 'reaches-line', () => m.getCanvas().style.cursor = '')
    })
    return () => { m.remove(); map.current = null }
  }, [jobId])

  return <div ref={box} className="h-[520px] w-full rounded-xl overflow-hidden border border-slate-200" />
}
