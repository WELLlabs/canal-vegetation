import { useMemo } from "react";

const HEX: Record<string, string> = {
  clear: "#16a34a",
  partial: "#d68c22",
  moderate: "#ea580c",
  full: "#dc2626",
};

/**
 * Top-down schematic of the canal channel at one chainage. Blockage mass
 * encroaches from both banks proportional to `pct`, so a viewer reads
 * "clear water" vs "obstructed" at a glance.
 */
export default function ChannelSection({
  status,
  pct,
  damage,
}: {
  status: string;
  pct: number;
  damage?: boolean;
}) {
  const hex = HEX[status] ?? "#64748b";
  const W = 600;
  const H = 340;
  const chW = W * 0.5;
  const chX = (W - chW) / 2;
  const top = 40;
  const bot = H - 40;
  const chH = bot - top;
  const enc = Math.min(0.46, (pct / 100) * 0.5);
  const sideW = chW * enc;

  const stipple = useMemo(() => {
    const dots: { x: number; y: number; r: number }[] = [];
    const n = Math.round(pct * 0.8);
    for (let i = 0; i < n; i++) {
      const left = Math.random() < 0.5;
      const x = left ? chX + 6 + Math.random() * sideW : chX + chW - 6 - Math.random() * sideW;
      const y = top + 6 + Math.random() * (chH - 12);
      dots.push({ x, y, r: 1 + Math.random() * 2 });
    }
    return dots;
  }, [pct, sideW, chH, chX, chW]);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" preserveAspectRatio="xMidYMid meet">
      <defs>
        <pattern id="cs-wave" width="18" height="10" patternUnits="userSpaceOnUse">
          <path d="M0 5 Q4.5 0 9 5 T18 5" stroke="#bfe9ff" fill="none" strokeWidth="1" />
        </pattern>
      </defs>
      <rect x="0" y="0" width={W} height={H} fill="#071c2c" />
      <rect x={chX} y={top} width={chW} height={chH} rx="6" fill="#0e2a3a" stroke="#12475f" strokeWidth="2" />
      <rect x={chX + 4} y={top + 4} width={chW - 8} height={chH - 8} rx="4" fill="#12678a" />
      <rect x={chX + 4} y={top + 4} width={chW - 8} height={chH - 8} rx="4" fill="url(#cs-wave)" opacity="0.5" />
      {pct > 0 && (
        <>
          <rect x={chX + 4} y={top + 4} width={Math.max(0, sideW)} height={chH - 8} fill={hex} opacity="0.9" />
          <rect x={chX + chW - 4 - sideW} y={top + 4} width={Math.max(0, sideW)} height={chH - 8} fill={hex} opacity="0.9" />
          {stipple.map((d, i) => (
            <circle key={i} cx={d.x} cy={d.y} r={d.r} fill={hex} opacity="0.8" />
          ))}
        </>
      )}
      <g stroke="#bfe9ff" strokeWidth="2" fill="none" opacity={pct > 70 ? 0.25 : 0.7}>
        <line x1={W / 2} y1={top - 14} x2={W / 2} y2={bot + 14} />
        <path d={`M${W / 2 - 6} ${bot + 6} L${W / 2} ${bot + 16} L${W / 2 + 6} ${bot + 6}`} />
      </g>
      <text x={chX - 8} y={H / 2} fill="#7fa0b3" fontSize="12" textAnchor="end" fontFamily="JetBrains Mono, monospace">bank</text>
      <text x={chX + chW + 8} y={H / 2} fill="#7fa0b3" fontSize="12" fontFamily="JetBrains Mono, monospace">bank</text>
      <text x={W / 2} y="24" fill="#e2edf3" fontSize="13" textAnchor="middle" fontFamily="Space Grotesk, sans-serif" fontWeight="700">
        {pct}% obstructed
      </text>
      {damage && (
        <g>
          <rect x={W - 132} y={H - 34} width="120" height="22" rx="5" fill="#dc2626" opacity="0.18" stroke="#dc2626" />
          <text x={W - 72} y={H - 19} fill="#fca5a5" fontSize="11" textAnchor="middle" fontFamily="JetBrains Mono, monospace">STRUCTURAL</text>
        </g>
      )}
    </svg>
  );
}
