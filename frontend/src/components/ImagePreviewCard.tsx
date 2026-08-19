import { RotateCcw, ScanLine } from "lucide-react";

interface ImagePreviewCardProps {
  imageUrl: string;
  fileName: string;
  isAnalyzing: boolean;
  progress: number;
  onReset: () => void;
}

export default function ImagePreviewCard({
  imageUrl,
  fileName,
  isAnalyzing,
  progress,
  onReset,
}: ImagePreviewCardProps) {
  return (
    <div className="animate-fade-up">
      <div className="reticle relative overflow-hidden rounded-xl border border-canal-100 bg-canal-950 shadow-sm">
        <img src={imageUrl} alt="Uploaded drone survey" className="max-h-[420px] w-full object-cover" />

        {isAnalyzing && (
          <div className="absolute inset-0 overflow-hidden bg-canal-950/30">
            <div className="animate-scan absolute inset-x-0 h-20 bg-gradient-to-b from-transparent via-teal-400/80 to-transparent shadow-[0_0_24px_4px_rgba(47,168,184,0.5)]" />
            <div className="absolute inset-0" style={{
              backgroundImage:
                "repeating-linear-gradient(0deg, rgba(255,255,255,0.05) 0px, rgba(255,255,255,0.05) 1px, transparent 1px, transparent 24px)",
            }} />
          </div>
        )}

        <div className="absolute left-3 top-3 flex items-center gap-1.5 rounded-md bg-canal-950/70 px-2.5 py-1 text-xs font-mono text-teal-300 backdrop-blur">
          <ScanLine className="h-3.5 w-3.5" />
          {fileName}
        </div>

        {!isAnalyzing && (
          <button
            onClick={onReset}
            className="absolute right-3 top-3 flex items-center gap-1.5 rounded-md bg-canal-950/70 px-2.5 py-1.5 text-xs font-medium text-white/90 backdrop-blur transition hover:bg-canal-950/90"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Replace
          </button>
        )}
      </div>

      {isAnalyzing && (
        <div className="mt-4">
          <div className="mb-2 flex items-center justify-between text-xs font-mono text-canal-600">
            <span>Running inference…</span>
            <span>{Math.min(100, Math.round(progress))}%</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-canal-100">
            <div
              className="h-full rounded-full bg-gradient-to-r from-teal-500 to-canal-700 transition-all duration-300 ease-out"
              style={{ width: `${Math.min(100, progress)}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
