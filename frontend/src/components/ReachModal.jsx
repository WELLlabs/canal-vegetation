import { useEffect } from 'react'
import ReachDetail from './ReachDetail.jsx'

// Centered pop-up over a dimmed, blurred page. Esc or click-outside closes it.
export default function ReachModal({ jobId, reach, onClose }) {
  useEffect(() => {
    if (!reach) return
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = '' }
  }, [reach])

  if (!reach) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
         role="dialog" aria-modal="true" onClick={onClose}>
      <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm cb-fade" />
      <div className="relative w-full max-w-lg max-h-[90vh] overflow-y-auto cb-pop"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-end mb-2">
          <button onClick={onClose} aria-label="Close"
            className="h-9 w-9 rounded-full bg-white shadow grid place-items-center text-slate-500 hover:text-slate-900">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6 6 18M6 6l12 12" /></svg>
          </button>
        </div>
        <ReachDetail jobId={jobId} reach={reach} />
      </div>
    </div>
  )
}
