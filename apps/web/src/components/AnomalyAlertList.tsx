import { AlertOctagon, CheckCircle2 } from "lucide-react";

interface AnomalyAlertListProps {
  flags: string[];
}

const FLAG_DESCRIPTIONS: Record<string, { title: string; detail: string }> = {
  FLAG_NEGATIVE_OPERATING_CASH_FLOW: {
    title: "Flujo de Caja Operativo Deficitario",
    detail: "La empresa generó flujo negativo en el último periodo, indicando incapacidad de cubrir operaciones normales.",
  },
  FLAG_OVERDRAFT_DETECTED: {
    title: "Sobregiros Bancarios Frecuentes",
    detail: "Se registraron extractos bancarios con saldo menor a cero, alertando tensión de tesorería y alto riesgo de cesación.",
  },
  FLAG_CLIENT_CONCENTRATION_RISK: {
    title: "Alta Concentración de Ingresos",
    detail: "Más del 30% de la facturación depende de un único cliente, aumentando la vulnerabilidad ante impagos de terceros.",
  },
};

export function AnomalyAlertList({ flags }: AnomalyAlertListProps) {
  if (!flags || flags.length === 0) {
    return (
      <div className="flex items-center gap-3 p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800">
        <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
        <div>
          <h4 className="text-sm font-bold">Sin alertas operativas ni de tesorería</h4>
          <p className="text-xs text-emerald-700">No se detectaron sobregiros, flujos negativos ni concentración extrema de clientes.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {flags.map((flag) => {
        const info = FLAG_DESCRIPTIONS[flag] || {
          title: flag,
          detail: "Alerta de riesgo detectada por el motor contable determinístico.",
        };

        return (
          <div
            key={flag}
            className="flex items-start gap-3 p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900"
          >
            <AlertOctagon className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="text-sm font-bold">{info.title}</h4>
              <p className="text-xs text-rose-700 mt-0.5">{info.detail}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
