import { Lightbulb } from "lucide-react";

export default function RecommendationsList({ items }: { items: string[] }) {
  return (
    <div className="rounded-xl border border-canal-100 bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-canal-500">
        <Lightbulb className="h-4 w-4" />
        AI Recommendations
      </div>
      <ol className="space-y-3">
        {items.map((item, i) => (
          <li key={i} className="flex gap-3 text-sm leading-relaxed text-canal-800">
            <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-canal-100 font-mono text-[11px] font-semibold text-canal-700">
              {i + 1}
            </span>
            {item}
          </li>
        ))}
      </ol>
    </div>
  );
}
