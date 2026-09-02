import { useRef, useState } from 'react'

export default function UploadDropzone({ label, hint, accept='.tif,.tiff', file, onFile, required, small }) {
  const inp = useRef(null)
  const [over, setOver] = useState(false)
  const pick = (f) => { if (f) onFile(f) }
  return (
    <div
      onDragOver={e=>{e.preventDefault();setOver(true)}}
      onDragLeave={()=>setOver(false)}
      onDrop={e=>{e.preventDefault();setOver(false);pick(e.dataTransfer.files?.[0])}}
      onClick={()=>inp.current?.click()}
      className={`cursor-pointer rounded-2xl border-2 border-dashed p-4 transition
        ${over ? 'border-brand-500 bg-brand-50' : file ? 'border-emerald-300 bg-emerald-50/50' : 'border-slate-300 bg-white hover:border-brand-400'}
        ${small ? 'py-3' : 'py-6'}`}>
      <input ref={inp} type="file" accept={accept} hidden onChange={e=>pick(e.target.files?.[0])} />
      <div className="flex items-center gap-3">
        <div className={`grid place-items-center rounded-xl ${file?'bg-emerald-100 text-emerald-700':'bg-brand-50 text-brand-700'} ${small?'h-9 w-9':'h-11 w-11'}`}>
          {file
            ? <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 6 9 17l-5-5"/></svg>
            : <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 16V4M6 10l6-6 6 6"/><path d="M4 20h16"/></svg>}
        </div>
        <div className="min-w-0">
          <div className="text-sm font-semibold text-slate-800">
            {label} {required && <span className="text-rose-500">*</span>}
          </div>
          <div className="text-xs text-slate-500 truncate">
            {file ? `${file.name} · ${(file.size/1e6).toFixed(1)} MB` : hint}
          </div>
        </div>
      </div>
    </div>
  )
}
