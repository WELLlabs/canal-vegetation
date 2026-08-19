interface ContourBackgroundProps {
  className?: string;
  variant?: "light" | "dark";
}

/**
 * Ambient contour-line texture referencing topographic survey maps used in
 * irrigation planning. Used sparingly behind the hero and section dividers.
 */
export default function ContourBackground({ className = "", variant = "light" }: ContourBackgroundProps) {
  const stroke = variant === "dark" ? "rgba(255,255,255,0.08)" : "rgba(15,59,90,0.06)";

  return (
    <svg
      className={`pointer-events-none absolute inset-0 h-full w-full ${className}`}
      viewBox="0 0 800 600"
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
    >
      <g fill="none" stroke={stroke} strokeWidth="1.5">
        <path d="M -50 500 Q 200 420 400 480 T 850 440" />
        <path d="M -50 440 Q 220 360 420 420 T 850 380" />
        <path d="M -50 380 Q 240 300 440 360 T 850 320" />
        <path d="M -50 320 Q 260 250 460 300 T 850 260" />
        <path d="M -50 60 Q 180 20 380 70 T 850 40" />
        <path d="M -50 120 Q 200 80 400 130 T 850 100" />
        <path d="M -50 180 Q 220 140 420 190 T 850 160" />
      </g>
    </svg>
  );
}
