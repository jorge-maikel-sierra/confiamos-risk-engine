import { ReactNode } from "react";
import { Check, AlertCircle, X } from "lucide-react";

interface MetricCardProps {
  label: string;
  value: string;
  description: string;
  status: "success" | "warning" | "danger" | "neutral";
  icon?: ReactNode;
}

export function MetricCard({ label, value, description, status, icon }: MetricCardProps) {
  const statusStyles = {
    success: {
      border: "border-emerald-200",
      bg: "bg-emerald-50/50",
      text: "text-emerald-700",
      badgeBg: "bg-emerald-100",
      icon: <Check className="w-3.5 h-3.5 text-emerald-700" />,
      label: "Saludable",
    },
    warning: {
      border: "border-amber-200",
      bg: "bg-amber-50/50",
      text: "text-amber-700",
      badgeBg: "bg-amber-100",
      icon: <AlertCircle className="w-3.5 h-3.5 text-amber-700" />,
      label: "Alerta",
    },
    danger: {
      border: "border-rose-200",
      bg: "bg-rose-50/50",
      text: "text-rose-700",
      badgeBg: "bg-rose-100",
      icon: <X className="w-3.5 h-3.5 text-rose-700" />,
      label: "Riesgo Crítico",
    },
    neutral: {
      border: "border-slate-200",
      bg: "bg-white",
      text: "text-slate-700",
      badgeBg: "bg-slate-100",
      icon: null,
      label: "Informativo",
    },
  }[status];

  return (
    <div className={`p-5 rounded-xl border bg-white shadow-sm flex flex-col justify-between ${statusStyles.border}`}>
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            {label}
          </span>
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold ${statusStyles.badgeBg} ${statusStyles.text}`}>
            {statusStyles.icon}
            {statusStyles.label}
          </span>
        </div>
        <div className="text-3xl font-extrabold text-slate-900 tracking-tight my-1">
          {value}
        </div>
      </div>
      <p className="text-xs text-slate-500 mt-2 font-medium">
        {description}
      </p>
    </div>
  );
}
