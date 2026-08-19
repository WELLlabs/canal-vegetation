import { Loader2, ScanSearch } from "lucide-react";

interface AnalyzeControlsProps {
  isAnalyzing: boolean;
  onAnalyze: () => void;
}

export default function AnalyzeControls({ isAnalyzing, onAnalyze }: AnalyzeControlsProps) {
  return (
    <button
      onClick={onAnalyze}
      disabled={isAnalyzing}
      className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-canal-800 px-6 py-3.5 text-sm font-semibold text-white transition hover:bg-canal-700 disabled:cursor-not-allowed disabled:opacity-70 sm:w-auto"
    >
      {isAnalyzing ? (
        <>
          <Loader2 className="h-4 w-4 animate-spin" />
          Analyzing Image…
        </>
      ) : (
        <>
          <ScanSearch className="h-4 w-4" />
          Analyze Image
        </>
      )}
    </button>
  );
}
