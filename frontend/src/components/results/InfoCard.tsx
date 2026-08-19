import type { ReactNode } from "react";

interface InfoCardProps {
  label: string;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
}

export default function InfoCard({ label, icon, children, className = "" }: InfoCardProps) {
  return (
    <div className={`rounded-xl border border-canal-100 bg-white p-6 shadow-sm ${className}`}>
      <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-canal-500">
        {icon}
        {label}
      </div>
      {children}
    </div>
  );
}
