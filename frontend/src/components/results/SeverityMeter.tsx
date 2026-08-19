import type { Severity } from "../../types";

const LEVELS: Severity[] = ["Low", "Medium", "High"];

const COLORS: Record<Severity, string> = {
  Low: "bg-success-500",
  Medium: "bg-warning-500",
  High: "bg-danger-500",
};

const TEXT_COLORS: Record<Severity, string> = {
  Low: "text-success-600",
  Medium: "text-warning-600",
  High: "text-danger-600",
};

export default function SeverityMeter({ severity }: { severity: Severity }) {
  const activeIndex = LEVELS.indexOf(severity);

  return (
    <div>
      <div className="flex gap-1.5">
        {LEVELS.map((level, i) => (
          <div
            key={level}
            className={`h-2.5 flex-1 rounded-full transition-colors ${
              i <= activeIndex ? COLORS[severity] : "bg-canal-100"
            }`}
          />
        ))}
      </div>
      <p className={`mt-2.5 font-mono text-2xl font-semibold ${TEXT_COLORS[severity]}`}>{severity}</p>
    </div>
  );
}
