import { ShieldAlert, AlertTriangle, ShieldCheck, Scale, Award } from "lucide-react";
import { CreditScorecardResult, RiskRatingCategory } from "@/types/underwriting";
import { formatCurrency } from "@/lib/utils";

interface ScorecardCardProps {
  scorecard?: CreditScorecardResult | null;
}

const CATEGORY_STYLES: Record<
  RiskRatingCategory,
  {
    badgeBg: string;
    badgeText: string;
    badgeBorder: string;
    pillBg: string;
    title: string;
    barColor: string;
  }
> = {
  A: {
    badgeBg: "bg-emerald-50",
    badgeText: "text-emerald-700",
    badgeBorder: "border-emerald-300",
    pillBg: "bg-emerald-600",
    title: "Categoría A — Riesgo Normal",
    barColor: "bg-emerald-500",
  },
  B: {
    badgeBg: "bg-blue-50",
    badgeText: "text-blue-700",
    badgeBorder: "border-blue-300",
    pillBg: "bg-blue-600",
    title: "Categoría B — Con Problemas Potenciales",
    barColor: "bg-blue-500",
  },
  C: {
    badgeBg: "bg-amber-50",
    badgeText: "text-amber-700",
    badgeBorder: "border-amber-300",
    pillBg: "bg-amber-600",
    title: "Categoría C — Deficiente",
    barColor: "bg-amber-500",
  },
  D: {
    badgeBg: "bg-orange-50",
    badgeText: "text-orange-700",
    badgeBorder: "border-orange-300",
    pillBg: "bg-orange-600",
    title: "Categoría D — Difícil Cobro / Dudoso",
    barColor: "bg-orange-500",
  },
  E: {
    badgeBg: "bg-rose-50",
    badgeText: "text-rose-700",
    badgeBorder: "border-rose-300",
    pillBg: "bg-rose-600",
    title: "Categoría E — Pérdida Irrecuperable",
    barColor: "bg-rose-500",
  },
};

export function ScorecardCard({ scorecard }: ScorecardCardProps) {
  if (!scorecard) {
    return (
      <div className="p-6 bg-white rounded-2xl border border-slate-200 text-center text-slate-400 text-xs">
        No se calculó matriz de scoring regulatorio para este expediente histórico.
      </div>
    );
  }

  const category = scorecard.rating_category;
  const config = CATEGORY_STYLES[category] || CATEGORY_STYLES.C;

  const breakdownItems = [
    {
      label: "Capacidad de Pago (DSCR)",
      weight: "35%",
      maxScore: 35.0,
      score: scorecard.breakdown.dscr_score,
      pct: Math.min(100, Math.max(0, (scorecard.breakdown.dscr_score / 35.0) * 100)),
    },
    {
      label: "Liquidez Inmediata & Runway",
      weight: "30%",
      maxScore: 30.0,
      score: scorecard.breakdown.liquidity_score,
      pct: Math.min(100, Math.max(0, (scorecard.breakdown.liquidity_score / 30.0) * 100)),
    },
    {
      label: "Concentración de Clientes & Sobregiros",
      weight: "20%",
      maxScore: 20.0,
      score: scorecard.breakdown.concentration_score,
      pct: Math.min(100, Math.max(0, (scorecard.breakdown.concentration_score / 20.0) * 100)),
    },
    {
      label: "Alineación con Auditoría de Riesgo IA",
      weight: "15%",
      maxScore: 15.0,
      score: scorecard.breakdown.ai_alignment_score,
      pct: Math.min(100, Math.max(0, (scorecard.breakdown.ai_alignment_score / 15.0) * 100)),
    },
  ];

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-6">
      {/* Resumen Principal de Rating y Provisión */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 items-stretch">
        {/* Rating Category Box */}
        <div
          className={`p-5 rounded-xl border flex flex-col justify-between ${config.badgeBg} ${config.badgeBorder}`}
        >
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                Calificación SBS / SES
              </span>
              <Award className={`w-4 h-4 ${config.badgeText}`} />
            </div>
            <div className="flex items-baseline gap-2 mt-1">
              <span className={`text-4xl font-black ${config.badgeText}`}>
                {category}
              </span>
              <span className="text-xs font-semibold text-slate-600">
                {scorecard.category_title || config.title}
              </span>
            </div>
          </div>
          <p className="text-[11px] font-medium text-slate-600 mt-3 pt-3 border-t border-slate-200/60">
            Escala regulatoria estándar de provisiones contables obligatorias.
          </p>
        </div>

        {/* Score Total */}
        <div className="p-5 rounded-xl border border-slate-200 bg-slate-50/50 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                Puntaje Global Multicriterio
              </span>
              <Scale className="w-4 h-4 text-slate-400" />
            </div>
            <div className="flex items-baseline gap-1 mt-1">
              <span className="text-3xl font-extrabold text-slate-900 tracking-tight">
                {scorecard.total_score.toFixed(1)}
              </span>
              <span className="text-sm font-bold text-slate-400">/ 100.0 pts</span>
            </div>
          </div>
          <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden mt-3">
            <div
              className={`h-full rounded-full ${config.barColor} transition-all duration-500`}
              style={{ width: `${Math.min(100, Math.max(0, scorecard.total_score))}%` }}
            />
          </div>
        </div>

        {/* Provisión Contable Requerida */}
        <div className="p-5 rounded-xl border border-slate-200 bg-slate-50/50 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                Provisión Contable Estimada
              </span>
              <span className="text-[11px] font-bold text-slate-700 bg-white px-2 py-0.5 rounded border border-slate-200">
                {scorecard.provision_percentage.toFixed(1)}%
              </span>
            </div>
            <div className="text-2xl font-black text-slate-900 tracking-tight mt-1">
              {formatCurrency(scorecard.estimated_provision_usd)}
            </div>
          </div>
          <p className="text-[11px] font-medium text-slate-500 mt-3 pt-3 border-t border-slate-200/60">
            Reserva de capital que la cooperativa debe inmovilizar en balance.
          </p>
        </div>
      </div>

      {/* Desglose de Factores Ponderados */}
      <div className="space-y-4 pt-2 border-t border-slate-100">
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
          Desglose Multicriterio de Factores Ponderados
        </h4>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {breakdownItems.map((item, idx) => (
            <div
              key={idx}
              className="p-3.5 bg-slate-50 rounded-xl border border-slate-100 space-y-2"
            >
              <div className="flex items-center justify-between text-xs font-semibold">
                <span className="text-slate-700">{item.label}</span>
                <span className="text-slate-900 font-bold font-mono">
                  {item.score.toFixed(1)} / {item.maxScore.toFixed(1)} pts
                </span>
              </div>
              <div className="w-full bg-slate-200 h-1.5 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full bg-blue-600 transition-all duration-500"
                  style={{ width: `${item.pct}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-[10px] text-slate-400 font-medium">
                <span>Ponderación: {item.weight}</span>
                <span>{item.pct.toFixed(0)}% del factor</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Justificación Regulatoria */}
      <div className="pt-2 border-t border-slate-100">
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
          Fundamentación Técnica y Justificación Regulatoria
        </h4>
        <div className="p-4 rounded-xl bg-slate-900 text-slate-200 text-xs leading-relaxed font-mono border border-slate-800">
          {scorecard.regulatory_justification}
        </div>
      </div>
    </div>
  );
}
