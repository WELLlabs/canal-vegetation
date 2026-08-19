import { UploadCloud, ScanSearch, FileCheck2 } from "lucide-react";

const STEPS = [
  {
    icon: UploadCloud,
    title: "Upload the survey image",
    body: "Drop in a drone image of the canal reach — top-down or oblique angles both work.",
  },
  {
    icon: ScanSearch,
    title: "Model runs inference",
    body: "The vision model scans for obstruction signatures — vegetation, silt, debris, or structural damage.",
  },
  {
    icon: FileCheck2,
    title: "Get a field-ready report",
    body: "Review status, severity, and affected area, then download a report for dispatch or records.",
  },
];

export default function HowItWorks() {
  return (
    <section id="how-it-works" className="border-t border-canal-100 bg-white">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <p className="text-xs font-semibold uppercase tracking-wider text-teal-600">Pipeline</p>
        <h2 className="mt-2 font-display text-3xl font-semibold tracking-tight text-canal-950">
          From aerial image to dispatch decision
        </h2>

        <div className="mt-12 grid grid-cols-1 gap-8 md:grid-cols-3">
          {STEPS.map((step, i) => (
            <div key={step.title} className="relative">
              {i < STEPS.length - 1 && (
                <div className="absolute right-[-16px] top-6 hidden h-px w-8 bg-canal-100 md:block" />
              )}
              <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-canal-100 text-canal-700">
                <step.icon className="h-5 w-5" />
              </div>
              <p className="mt-4 font-mono text-xs text-canal-500">Step {i + 1}</p>
              <h3 className="mt-1 font-display text-lg font-semibold text-canal-950">{step.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-canal-600">{step.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
