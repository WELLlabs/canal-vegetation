import { AlertTriangle, CheckCircle2 } from "lucide-react";

export default function StatusBadge({ detected }: { detected: boolean }) {
  if (detected) {
    return (
      <div className="inline-flex items-center gap-2 rounded-full bg-danger-100 px-4 py-1.5 text-sm font-semibold text-danger-600">
        <AlertTriangle className="h-4 w-4" />
        Blockage Detected
      </div>
    );
  }
  return (
    <div className="inline-flex items-center gap-2 rounded-full bg-success-100 px-4 py-1.5 text-sm font-semibold text-success-600">
      <CheckCircle2 className="h-4 w-4" />
      Not Detected
    </div>
  );
}
