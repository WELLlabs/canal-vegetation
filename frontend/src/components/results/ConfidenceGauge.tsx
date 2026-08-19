interface ConfidenceGaugeProps {
  confidence: number; // 0-100
}

export default function ConfidenceGauge({ confidence }: ConfidenceGaugeProps) {
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (confidence / 100) * circumference;

  const color =
    confidence >= 85 ? "var(--color-teal-500)" : confidence >= 60 ? "var(--color-warning-500)" : "var(--color-danger-500)";

  return (
    <div className="flex flex-col items-center justify-center">
      <svg width="140" height="140" viewBox="0 0 140 140" className="-rotate-90">
        <circle cx="70" cy="70" r={radius} fill="none" stroke="var(--color-canal-100)" strokeWidth="10" />
        <circle
          cx="70"
          cy="70"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 1s cubic-bezier(0.16,1,0.3,1)" }}
        />
      </svg>
      <div className="-mt-[92px] flex flex-col items-center">
        <span className="font-mono text-3xl font-semibold text-canal-950">{confidence.toFixed(1)}</span>
        <span className="text-xs font-medium uppercase tracking-wide text-canal-500">% confidence</span>
      </div>
    </div>
  );
}
