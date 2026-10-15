import { CheckCircle2, AlertTriangle, XCircle, Clock, ShieldAlert } from "lucide-react";
import { CreditRecommendation } from "@/types/underwriting";

interface VerdictBadgeProps {
  recommendation?: CreditRecommendation | null;
  step?: string;
  isCompleted?: boolean;
}

export function VerdictBadge({ recommendation, step, isCompleted }: VerdictBadgeProps) {
  if (recommendation === "APROBADO") {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
        <CheckCircle2 className="w-3.5 h-3.5" />
        Aprobado
      </span>
    );
  }

  if (recommendation === "APROBADO_CONDICIONADO") {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
        <AlertTriangle className="w-3.5 h-3.5" />
        Condicionado
      </span>
    );
  }

  if (recommendation === "RECHAZADO") {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
        <XCircle className="w-3.5 h-3.5" />
        Rechazado
      </span>
    );
  }

  if (step === "PENDING_HUMAN_REVIEW" && !isCompleted) {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 animate-pulse">
        <Clock className="w-3.5 h-3.5" />
        Revisión Comité
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
      <ShieldAlert className="w-3.5 h-3.5" />
      {step || "En Evaluación"}
    </span>
  );
}
