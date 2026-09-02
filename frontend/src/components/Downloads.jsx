const API = import.meta.env.VITE_API_URL || '/api'
function Btn({ href, children }) {
  return <a href={href} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:border-brand-400 hover:text-brand-700">
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 3v12M7 11l5 5 5-5"/><path d="M5 21h14"/></svg>{children}</a>
}
export default function Downloads({ jobId }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm font-medium text-slate-500 mr-1">Download:</span>
      <Btn href={`${API}/jobs/${jobId}/csv`}>CSV</Btn>
      <Btn href={`${API}/jobs/${jobId}/geojson`}>GeoJSON</Btn>
    </div>
  )
}
