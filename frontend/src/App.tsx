import { useCallback, useState } from "react";
import { AlertCircle } from "lucide-react";
import NavBar from "./components/NavBar";
import Hero from "./components/Hero";
import HowItWorks from "./components/HowItWorks";
import Footer from "./components/Footer";
import UploadZone from "./components/UploadZone";
import ImagePreviewCard from "./components/ImagePreviewCard";
import AnalyzeControls from "./components/AnalyzeControls";
import AlignmentUpload from "./components/AlignmentUpload";
import ResultsDashboard from "./components/results/ResultsDashboard";
import { analyzeImage } from "./api/analyzeImage";
import type { AnalysisResult, WorkflowStage } from "./types";

export default function App() {
  const [stage, setStage] = useState<WorkflowStage>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [alignmentFiles, setAlignmentFiles] = useState<File[]>([]);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [currentStage, setCurrentStage] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileSelected = useCallback((selected: File) => {
    setFile(selected);
    setAlignmentFiles([]);
    setImageUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      const previewable = /\.(png|jpe?g|webp)$/i.test(selected.name);
      return previewable ? URL.createObjectURL(selected) : null;
    });
    setResult(null);
    setError(null);
    setStage("preview");
  }, []);

  const handleReset = useCallback(() => {
    if (imageUrl) URL.revokeObjectURL(imageUrl);
    setFile(null);
    setAlignmentFiles([]);
    setImageUrl(null);
    setResult(null);
    setError(null);
    setProgress(0);
    setCurrentStage(null);
    setStage("idle");
  }, [imageUrl]);

  const handleAnalyze = useCallback(async () => {
    if (!file) return;
    setStage("analyzing");
    setProgress(0);
    setCurrentStage("upload");
    setError(null);
    try {
      const analysis = await analyzeImage(
        file,
        (percent, pipelineStage) => {
          setProgress(percent);
          if (pipelineStage) setCurrentStage(pipelineStage);
        },
        { alignmentFiles }
      );
      setResult(analysis);
      setStage("results");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong during analysis.");
      setStage("error");
    }
  }, [file, alignmentFiles]);

  return (
    <div className="min-h-screen bg-canal-50">
      <NavBar />
      <Hero />

      <section id="upload" className="relative">
        <div className="mx-auto max-w-4xl px-6 py-20">
          <div className="mb-10 text-center">
            <p className="text-xs font-semibold uppercase tracking-wider text-teal-600">Run a Scan</p>
            <h2 className="mt-2 font-display text-3xl font-semibold tracking-tight text-canal-950">
              Upload a GeoTIFF to begin
            </h2>
            <p className="mx-auto mt-3 max-w-lg text-sm text-canal-600">
              Upload a GeoTIFF orthomosaic. Optionally add a canal alignment (GeoJSON or shapefile) for
              corridor-based reaches. Results are model or alignment-assisted — not field verified.
            </p>
          </div>

          {stage === "idle" && <UploadZone onFileSelected={handleFileSelected} />}

          {(stage === "preview" || stage === "analyzing" || stage === "error") && file && (
            <div className="space-y-6">
              <ImagePreviewCard
                imageUrl={imageUrl}
                fileName={file.name}
                isAnalyzing={stage === "analyzing"}
                progress={progress}
                currentStage={currentStage}
                onReset={handleReset}
              />

              {stage !== "analyzing" && (
                <AlignmentUpload files={alignmentFiles} onChange={setAlignmentFiles} />
              )}

              {stage === "error" && error && (
                <div className="flex items-start gap-3 rounded-lg border border-danger-100 bg-danger-100/60 p-4 text-sm text-danger-600">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                  <div>
                    <p className="font-semibold">Analysis failed</p>
                    <p className="mt-0.5 text-danger-600/90">{error}</p>
                  </div>
                </div>
              )}

              {stage !== "analyzing" && (
                <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-between">
                  <p className="text-xs font-mono text-canal-500">
                    {file.name} · {(file.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                  <AnalyzeControls isAnalyzing={false} onAnalyze={handleAnalyze} />
                </div>
              )}

              {stage === "analyzing" && (
                <div className="flex justify-center sm:justify-end">
                  <AnalyzeControls isAnalyzing={true} onAnalyze={handleAnalyze} />
                </div>
              )}
            </div>
          )}

          {stage === "results" && result && file && (
            <ResultsDashboard result={result} imageUrl={imageUrl ?? ""} fileName={file.name} />
          )}

          {stage === "results" && (
            <div className="mt-8 text-center">
              <button
                onClick={handleReset}
                className="text-sm font-medium text-canal-600 underline decoration-canal-200 underline-offset-4 transition hover:text-teal-600"
              >
                Run another scan
              </button>
            </div>
          )}
        </div>
      </section>

      <HowItWorks />
      <Footer />
    </div>
  );
}
