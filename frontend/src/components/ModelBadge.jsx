// Read-only badge for the single fixed model. There is no model selector.
export default function ModelBadge({ model, compact }) {
  const ok = model?.installed
  const dot = ok ? 'bg-emerald-500' : 'bg-amber-500'
  if (compact) {
    return (
      <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm">
        <span className={`h-2 w-2 rounded-full ${dot}`} />
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-slate-500"><rect x="3" y="11" width="18" height="10" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
        <span className="font-medium text-slate-700">
          {ok ? `Model ${model.version}` : 'Model not installed'}
        </span>
      </div>
    )
  }
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-slate-900 font-semibold">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-brand-700"><rect x="3" y="11" width="18" height="10" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
          Approved model
        </div>
        <span className="text-xs font-semibold rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">Fixed · not selectable</span>
      </div>
      {ok ? (
        <div className="mt-3 grid grid-cols-2 gap-y-2 text-sm">
          <span className="text-slate-500">Version</span><span className="text-right font-medium">{model.version}</span>
          <span className="text-slate-500">Type</span><span className="text-right font-medium capitalize">{model.kind}</span>
          <span className="text-slate-500">File</span><span className="text-right font-mono text-xs truncate">{model.name}</span>
          <span className="text-slate-500">Checksum</span><span className="text-right font-mono text-xs">{model.checksum}</span>
          <span className="text-slate-500 col-span-2 pt-1">Outputs</span>
          <div className="col-span-2 flex flex-wrap gap-1.5">
            {(model.classes||[]).map(c => <span key={c} className="text-xs rounded-md bg-brand-50 text-brand-800 px-2 py-0.5 capitalize">{c}</span>)}
          </div>
        </div>
      ) : (
        <p className="mt-3 text-sm text-slate-500">
          Drop the approved trained file into <code className="text-xs bg-slate-100 px-1 py-0.5 rounded">backend/app/config/models/</code> and reload. The app always uses that one file.
        </p>
      )}
    </div>
  )
}
