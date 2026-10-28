import { useEffect, useRef, useState } from 'react'
import Header from './components/Header.jsx'
import ModelBadge from './components/ModelBadge.jsx'
import PipelineSteps from './components/PipelineSteps.jsx'
import UploadDropzone from './components/UploadDropzone.jsx'
import ResultSummary from './components/ResultSummary.jsx'
import ResultsView from './components/ResultsView.jsx'
import { getModel, getJob, runPrediction } from './lib/api.js'

const RUNNING = new Set(['queued', 'loading_model', 'running'])
const PHASES = ['Upload', 'Model', 'Reaches', 'Silt', 'Report']

export default function App() {
  const [model, setModel] = useState(null)
  const [align, setAlign] = useState(null)
  const [ortho, setOrtho] = useState(null)
  const [dsm, setDsm] = useState(null)
  const [dtm, setDtm] = useState(null)
  const [job, setJob] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadPct, setUploadPct] = useState(0)
  const [error, setError] = useState('')
  const [apiDown, setApiDown] = useState(false)
  const timer = useRef(null)

  useEffect(() => {
    (async () => {
      try { setModel(await getModel()); setApiDown(false) }
      catch { setModel({ installed: false }); setApiDown(true) }
    })()
    return () => clearTimeout(timer.current)
  }, [])

  const siltReady = dsm && dtm
  const running = job && RUNNING.has(job.state)
  const busy = uploading || running
  const canRun = ortho && model?.installed && !busy
  const completedOverlap = job?.state === 'completed' && job.summary?.overlap
  const completedNoOverlap = job?.state === 'completed' && !job.summary?.overlap
  const showInputs = !busy && !completedOverlap && !completedNoOverlap

  const poll = (id) => {
    getJob(id).then(j => {
      setJob(j)
      if (RUNNING.has(j.state)) timer.current = setTimeout(() => poll(id), 1200)
    }).catch(() => { timer.current = setTimeout(() => poll(id), 2000) })
  }

  const submit = async () => {
    setError(''); setJob(null); setUploadPct(0); setUploading(true)
    try {
      const j = await runPrediction({ alignment: align, orthophoto: ortho, dsm, dtm,
        onUploadProgress: (pct) => setUploadPct(pct) })
      setUploading(false); setJob(j); poll(j.id)
    } catch (e) { setUploading(false); setError(e.message) }
  }

  const reset = () => {
    clearTimeout(timer.current)
    setJob(null); setUploading(false); setUploadPct(0); setError('')
    setOrtho(null); setAlign(null); setDsm(null); setDtm(null)
  }

  // Which phase is active, for the processing stepper.
  const phaseIdx = uploading ? 0
    : job?.state === 'loading_model' ? 1
    : job?.state === 'running' ? (String(job.message).toLowerCase().includes('silt') ? 3 : 2)
    : job?.state === 'completed' ? 4 : 0
  const pct = uploading ? uploadPct : (job?.progress || 0)

  return (
    <div className="min-h-screen">
      <Header model={model} />
      {busy && (
        <div className="h-1 w-full bg-brand-100 overflow-hidden">
          <div className="h-full bg-brand-500 transition-all duration-500"
               style={{ width: `${uploading ? (uploadPct || 8) : (job?.progress || 0)}%` }} />
        </div>
      )}

      <section className="hero-water border-b border-slate-200">
        <div className="mx-auto max-w-6xl px-5 py-10">
          <span className="inline-flex items-center gap-2 rounded-full bg-white border border-brand-100 px-3 py-1 text-xs font-semibold text-brand-800">
            <span className="h-2 w-2 rounded-full bg-brand-500" /> Drone survey to canal health, in minutes
          </span>
          <h1 className="mt-4 text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900" style={{ textWrap: 'balance' }}>
            Find canal blockages from your drone imagery.
          </h1>
          <p className="mt-2 max-w-2xl text-slate-600">
            Upload a georeferenced orthophoto. The app finds the canal automatically
            from the national canal layer and the approved model scores every 50-metre
            reach as clear, partial, moderate, or blocked. Add elevation files to also
            estimate silt.
          </p>
          <div className="mt-6"><PipelineSteps /></div>
        </div>
      </section>

      {apiDown && (
        <div className="mx-auto max-w-6xl px-5 pt-6">
          <div className="rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-sm px-4 py-3">
            <span className="font-semibold">Backend not reachable.</span> The model badge comes from the API at <code className="bg-amber-100 px-1 rounded">/api</code> (port 8000), which isn't responding. Start the backend (see README), or run <code className="bg-amber-100 px-1 rounded">docker compose up --build</code> and open <b>http://localhost:8080</b>.
          </div>
        </div>
      )}

      {/* ---------- INPUTS (idle only) ---------- */}
      {showInputs && (
        <main className="mx-auto max-w-6xl px-5 py-8 grid lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <div className="rounded-2xl border border-slate-200 bg-white p-5">
              <h2 className="font-semibold text-slate-900">1 · Upload imagery</h2>
              <p className="text-sm text-slate-500 mb-4">Any GeoTIFF orthophoto works; the app reads its location from the file and finds the canal from the national layer. Elevation files are optional.</p>
              <UploadDropzone label="Drone orthophoto (GeoTIFF)" hint="Drag & drop or click to browse, .tif / .tiff" required file={ortho} onFile={setOrtho} />
              <div className="mt-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-slate-700">Canal alignment</span>
                  <span className="text-xs font-medium rounded-full px-2 py-0.5 bg-slate-100 text-slate-500">Optional · override</span>
                </div>
                <UploadDropzone label="Own canal alignment (zipped shapefile or GeoJSON)" hint="Optional. Leave empty to auto-select from the national layer" accept=".zip,.geojson,.json" file={align} onFile={setAlign} />
                <p className="mt-2 text-[11px] text-slate-400">Leave this empty and the canal under your orthophoto is picked automatically. Upload one only to override the national layer for this run.</p>
              </div>
              <div className="mt-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-slate-700">Optional · silt analysis</span>
                  <span className={`text-xs font-medium rounded-full px-2 py-0.5 ${siltReady ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                    {siltReady ? 'Silt will be included' : 'Add DSM + DTM to unlock'}
                  </span>
                </div>
                <div className="grid sm:grid-cols-2 gap-3">
                  <UploadDropzone small label="DSM, surface" hint="Elevation .tif" file={dsm} onFile={setDsm} />
                  <UploadDropzone small label="DTM, terrain" hint="Elevation .tif" file={dtm} onFile={setDtm} />
                </div>
              </div>
            </div>

            {error && <div className="rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-sm px-4 py-3">{error}</div>}
          </div>

          <div className="space-y-6">
            <ModelBadge model={model} />
            <div className="rounded-2xl border border-slate-200 bg-white p-5">
              <h3 className="font-semibold text-slate-900">2 · Run analysis</h3>
              <ul className="mt-3 space-y-2 text-sm">
                <li className="flex items-center gap-2">{check(ortho)} Orthophoto added</li>
                <li className="flex items-center gap-2">{dot(true)} Canal {align ? 'from your alignment' : 'auto-selected'}</li>
                <li className="flex items-center gap-2">{check(model?.installed)} Approved model ready</li>
                <li className="flex items-center gap-2">{dot(siltReady)} Silt files {siltReady ? 'added' : '(optional)'}</li>
              </ul>
              <button onClick={submit} disabled={!canRun}
                className={`mt-4 w-full rounded-xl px-4 py-3 font-semibold text-white transition
                  ${canRun ? 'bg-brand-600 hover:bg-brand-700 shadow-soft' : 'bg-slate-300 cursor-not-allowed'}`}>
                Run blockage analysis
              </button>
              <p className="mt-2 text-[11px] text-slate-400 text-center">Once started, inputs lock until the result is ready.</p>
            </div>
          </div>
        </main>
      )}

      {/* ---------- PROCESSING (busy only) ---------- */}
      {busy && (
        <main className="mx-auto max-w-2xl px-5 py-12">
          <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm text-center">
            <div className="mx-auto h-16 w-16 rounded-2xl bg-brand-50 grid place-items-center">
              <Spinner big />
            </div>
            <h2 className="mt-4 text-xl font-bold text-slate-900">
              {uploading ? 'Uploading orthophoto' : 'Analysing canal'}
            </h2>
            <p className="text-sm text-slate-500 mt-1">
              {uploading
                ? (ortho ? `${(ortho.size / 1e6).toFixed(0)} MB · keep this tab open` : 'Sending imagery to the server')
                : (job?.message || 'Working…')}
            </p>

            <div className="mt-6 max-w-md mx-auto">
              <div className="flex justify-between text-xs mb-1">
                <span className="font-medium text-slate-600">{uploading ? 'Upload' : 'Processing'}</span>
                <span className="tabular-nums text-slate-500">{pct == null ? '' : `${pct}%`}</span>
              </div>
              <div className="h-3 rounded-full bg-slate-100 overflow-hidden">
                {pct == null
                  ? <div className="h-full w-1/3 bg-brand-500 rounded-full animate-pulse" />
                  : <div className="h-full bg-brand-500 rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />}
              </div>
            </div>

            {/* phase stepper */}
            <div className="mt-6 flex items-center justify-center gap-2 flex-wrap">
              {PHASES.map((label, i) => {
                const active = i === phaseIdx, done = i < phaseIdx
                return (
                  <div key={label} className="flex items-center gap-2">
                    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium
                      ${active ? 'bg-brand-600 text-white' : done ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-400'}`}>
                      {done
                        ? <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M20 6 9 17l-5-5" /></svg>
                        : <span className={`h-1.5 w-1.5 rounded-full ${active ? 'bg-white animate-pulse' : 'bg-slate-300'}`} />}
                      {label}
                    </span>
                    {i < PHASES.length - 1 && <span className="text-slate-300">›</span>}
                  </div>
                )
              })}
            </div>
            {job?.id && <p className="mt-4 text-[11px] text-slate-400">Job {job.id}</p>}
          </div>
        </main>
      )}

      {/* ---------- NO-OVERLAP result ---------- */}
      {completedNoOverlap && (
        <main className="mx-auto max-w-2xl px-5 py-12 space-y-4">
          <ResultSummary summary={job.summary} />
          <button onClick={reset} className="w-full rounded-xl px-4 py-3 font-semibold text-white bg-brand-600 hover:bg-brand-700 shadow-soft">
            Try another orthophoto
          </button>
        </main>
      )}

      {/* ---------- RESULTS (ready only) ---------- */}
      {completedOverlap && (
        <section className="mx-auto max-w-6xl px-5 py-8 pb-14" id="results-map">
          <div className="flex justify-end mb-3">
            <button onClick={reset}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:border-brand-400 hover:text-brand-700">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 5v14M5 12h14" /></svg>
              New analysis
            </button>
          </div>
          {job.summary?.model_warning && <ModelWarning text={job.summary.model_warning} />}
          <ResultsView jobId={job.id} summary={job.summary} />
        </section>
      )}

      <footer className="border-t border-slate-200 py-6 text-center text-xs text-slate-400">
        WELL Labs · Canal Intelligence, the running model is fixed; feedback trains the next approved version.
      </footer>
    </div>
  )
}

function ModelWarning({ text }) {
  return (
    <div className="mb-4 rounded-xl bg-amber-50 border border-amber-300 text-amber-900 text-sm px-4 py-3">
      <span className="font-semibold">Scores unreliable for this canal. </span>{text}
    </div>
  )
}
function check(ok) {
  return ok
    ? <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="text-emerald-500"><path d="M20 6 9 17l-5-5" /></svg>
    : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-slate-300"><circle cx="12" cy="12" r="9" /></svg>
}
function Spinner({ big }) {
  const s = big ? 30 : 16
  return <svg className="animate-spin text-brand-600" width={s} height={s} viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" strokeOpacity="0.25" /><path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" /></svg>
}
function dot(ok) { return <span className={`h-3.5 w-3.5 rounded-full ${ok ? 'bg-emerald-500' : 'bg-slate-200'}`} /> }
