"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  BadgeAlert,
  Calculator,
  Calendar,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  DollarSign,
  HelpCircle,
  Percent,
  RefreshCw,
  Scale,
  ShieldAlert,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import { fetchPricingProposal, generatePricingProposal } from "@/lib/api";
import {
  AmortizationSystem,
  PaymentPeriodQuota,
  PricingProposal,
} from "@/types/underwriting";
import { formatCurrency } from "@/lib/utils";

interface PricingAmortizationCardProps {
  applicationId: string;
  initialPricing?: PricingProposal | null;
}

export function PricingAmortizationCard({
  applicationId,
  initialPricing,
}: PricingAmortizationCardProps) {
  const [pricing, setPricing] = useState<PricingProposal | null>(
    initialPricing || null
  );
  const [loading, setLoading] = useState(!initialPricing);
  const [calculating, setCalculating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Estados interactivos para simulación
  const [selectedSystem, setSelectedSystem] = useState<AmortizationSystem>(
    initialPricing?.amortization_system || "FRENCH"
  );
  const [termMonths, setTermMonths] = useState<number>(
    initialPricing?.term_months || 24
  );
  const [showFullSchedule, setShowFullSchedule] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchPricingProposal(applicationId);
      setPricing(data);
      setSelectedSystem(data.amortization_system);
      setTermMonths(data.term_months);
    } catch (err: any) {
      setError(err.message || "Error al cargar la propuesta de pricing");
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => {
    if (!initialPricing) {
      loadData();
    }
  }, [initialPricing, loadData]);

  const handleRecalculate = async (
    systemToUse?: AmortizationSystem,
    termToUse?: number
  ) => {
    try {
      setCalculating(true);
      setError(null);
      const sys = systemToUse || selectedSystem;
      const term = termToUse !== undefined ? termToUse : termMonths;
      setSelectedSystem(sys);
      setTermMonths(term);

      const data = await generatePricingProposal(applicationId, {
        amortization_system: sys,
        term_months_override: Number(term),
      });
      setPricing(data);
      setSelectedSystem(data.amortization_system);
      setTermMonths(data.term_months);
    } catch (err: any) {
      setError(err.message || "Error al recalcular el pricing");
    } finally {
      setCalculating(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 bg-white rounded-2xl border border-slate-200 text-center">
        <RefreshCw className="w-6 h-6 mx-auto animate-spin mb-2 text-blue-600" />
        <p className="text-xs text-slate-500 font-medium">Calculando estructura de pricing y amortizaciones...</p>
      </div>
    );
  }

  if (error && !pricing) {
    return (
      <div className="p-6 bg-rose-50 border border-rose-200 rounded-2xl text-center text-rose-700 text-xs">
        <AlertTriangle className="w-6 h-6 mx-auto mb-2 text-rose-500" />
        <p className="font-semibold">{error}</p>
        <button
          onClick={loadData}
          className="mt-3 px-3 py-1.5 bg-rose-600 text-white rounded-lg font-bold hover:bg-rose-700 transition"
        >
          Reintentar
        </button>
      </div>
    );
  }

  if (!pricing) return null;

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden space-y-6 p-6">
      {/* Alerta Destacada de Usura (Decisión de diseño: Tope automático + Alerta visual) */}
      {pricing.exceeds_usury_cap && (
        <div className="p-4 bg-amber-500/10 border-2 border-amber-500/60 rounded-xl text-amber-950 flex items-start gap-3">
          <BadgeAlert className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div className="text-xs leading-relaxed space-y-1">
            <span className="font-extrabold uppercase tracking-wide text-amber-900 block">
              Alerta Regulatoria: TEA Ajustada al Límite Legal de Usura
            </span>
            <p className="text-amber-900/90 font-medium">
              La tasa técnica requerida por riesgo puro fue de{" "}
              <strong className="font-bold underline">{pricing.uncapped_tea.toFixed(2)}% E.A.</strong>,
              superando el límite legal máximo ({pricing.usury_cap_tea.toFixed(2)}% E.A.). El motor aplicó un
              recorte automático obligatorio de{" "}
              <strong className="font-bold">-{pricing.usury_adjustment_delta.toFixed(2)}% E.A.</strong> Fijando la
              tasa en {pricing.applied_tea.toFixed(2)}% E.A. Se sugiere exigir colaterales admisibles para mitigar la
              pérdida esperada (${pricing.expected_loss_usd.toFixed(2)} USD).
            </p>
          </div>
        </div>
      )}

      {/* 1. Indicadores Principales de Tasa y Cuotas */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Tasa Efectiva Anual (TEA) */}
        <div
          className={`p-4 rounded-xl border ${
            pricing.exceeds_usury_cap
              ? "bg-amber-50 border-amber-300"
              : "bg-blue-50 border-blue-200"
          }`}
        >
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Tasa Aprobada (TEA)
            </span>
            <Percent className="w-4 h-4 text-blue-600" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-black text-slate-900">
              {pricing.applied_tea.toFixed(2)}%
            </span>
            <span className="text-xs font-semibold text-slate-500">E.A.</span>
          </div>
          <p className="text-[11px] font-medium text-slate-600 mt-1">
            Tasa Mensual: <strong>{pricing.monthly_effective_rate_pct.toFixed(2)}% M.V.</strong>
          </p>
        </div>

        {/* Primera Cuota Mensual */}
        <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/70">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Primera Cuota Mensual
            </span>
            <DollarSign className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-black text-emerald-700">
              {formatCurrency(pricing.first_month_quota_usd)}
            </span>
          </div>
          <p className="text-[11px] font-medium text-slate-500 mt-1">
            Incluye Seguro de Cartera (0.12%)
          </p>
        </div>

        {/* Total Intereses */}
        <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/70">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Intereses Totales
            </span>
            <TrendingUp className="w-4 h-4 text-slate-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-black text-slate-900">
              {formatCurrency(pricing.total_interest_usd)}
            </span>
          </div>
          <p className="text-[11px] font-medium text-slate-500 mt-1">
            Plazo Total: {pricing.term_months} Meses
          </p>
        </div>

        {/* Costo Total del Crédito */}
        <div className="p-4 rounded-xl border border-indigo-200 bg-indigo-50/60">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-900">
              Costo Total Contractual
            </span>
            <Calculator className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-black text-indigo-800">
              {formatCurrency(pricing.total_cost_of_credit_usd)}
            </span>
          </div>
          <p className="text-[11px] font-semibold text-indigo-900 mt-1">
            Capital: {formatCurrency(pricing.requested_amount_usd)}
          </p>
        </div>
      </div>

      {/* 2. Desglose Aditivo de Componentes de la Tasa */}
      <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-3">
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
          <Scale className="w-4 h-4 text-slate-500" />
          <span>Estructura de Descomposición Económica de la Tasa (TEA)</span>
        </h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          <div className="p-2.5 bg-white rounded-lg border border-slate-200">
            <span className="text-slate-500 block text-[10px] uppercase font-bold">Costo Fondeo (COF)</span>
            <span className="text-sm font-bold text-slate-800">+{pricing.cost_of_funds_ea.toFixed(2)}%</span>
            <p className="text-[10px] text-slate-400">Captaciones CDAT/Ahorro</p>
          </div>
          <div className="p-2.5 bg-white rounded-lg border border-slate-200">
            <span className="text-slate-500 block text-[10px] uppercase font-bold">Margen Operativo (OPEX)</span>
            <span className="text-sm font-bold text-slate-800">+{pricing.opex_spread_ea.toFixed(2)}%</span>
            <p className="text-[10px] text-slate-400">Gastos de administración</p>
          </div>
          <div className="p-2.5 bg-white rounded-lg border border-slate-200">
            <span className="text-slate-500 block text-[10px] uppercase font-bold">Prima por Riesgo (EL)</span>
            <span className="text-sm font-bold text-blue-700">+{pricing.expected_loss_rate_ea.toFixed(2)}%</span>
            <p className="text-[10px] text-slate-400">
              EL: {formatCurrency(pricing.expected_loss_usd)} (PD: {pricing.probability_of_default_pct}% | LGD:{" "}
              {pricing.loss_given_default_pct}%)
            </p>
          </div>
          <div className="p-2.5 bg-white rounded-lg border border-slate-200">
            <span className="text-slate-500 block text-[10px] uppercase font-bold">Margen RAROC</span>
            <span className="text-sm font-bold text-emerald-700">+{pricing.raroc_target_ea.toFixed(2)}%</span>
            <p className="text-[10px] text-slate-400">Retorno sobre capital cooperativo</p>
          </div>
        </div>
      </div>

      {/* 3. Panel de Simulación y Selección de Sistema de Amortización */}
      <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="space-y-1">
            <span className="text-xs font-bold text-slate-800">Modalidad del Plan de Amortización</span>
            <p className="text-[11px] text-slate-500">
              Seleccioná el sistema de cuotas para ajustar el flujo financiero al ciclo operativo del socio.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <div className="inline-flex rounded-lg border border-slate-300 p-0.5 bg-white">
              <button
                type="button"
                onClick={() => handleRecalculate("FRENCH", termMonths)}
                disabled={calculating}
                className={`px-3 py-1.5 text-xs font-bold rounded-md transition ${
                  selectedSystem === "FRENCH"
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Francés (Cuota Fija)
              </button>
              <button
                type="button"
                onClick={() => handleRecalculate("GERMAN", termMonths)}
                disabled={calculating}
                className={`px-3 py-1.5 text-xs font-bold rounded-md transition ${
                  selectedSystem === "GERMAN"
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Alemán (Amortización Fija)
              </button>
            </div>

            {calculating && <RefreshCw className="w-4 h-4 animate-spin text-blue-600 ml-1" />}
          </div>
        </div>

        {/* Control de Plazo Rápido */}
        <div className="flex items-center gap-4 pt-2 border-t border-slate-200/80">
          <div className="flex items-center gap-2 text-xs text-slate-700">
            <Calendar className="w-4 h-4 text-slate-400" />
            <span className="font-semibold">Plazo Simulado:</span>
          </div>
          <div className="flex items-center gap-1.5">
            {[12, 24, 36, 48, 60].map((months) => (
              <button
                key={months}
                type="button"
                onClick={() => handleRecalculate(selectedSystem, months)}
                disabled={calculating}
                className={`px-2.5 py-1 text-xs font-bold rounded-lg border transition ${
                  termMonths === months
                    ? "bg-slate-900 text-white border-slate-900"
                    : "bg-white text-slate-600 border-slate-200 hover:bg-slate-100"
                }`}
              >
                {months}m
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 4. Tabla de Amortización Desplegable */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
            <Calendar className="w-4 h-4 text-slate-500" />
            <span>
              Plan de Pagos Mensual ({pricing.amortization_schedule.length} Periodos — Sistema{" "}
              {pricing.amortization_system === "FRENCH" ? "Francés" : "Alemán"})
            </span>
          </h3>
          <button
            onClick={() => setShowFullSchedule(!showFullSchedule)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-slate-700 bg-slate-100 hover:bg-slate-200 transition"
          >
            <span>{showFullSchedule ? "Ver Menos Cuotas" : "Ver Tabla Completa"}</span>
            {showFullSchedule ? (
              <ChevronUp className="w-3.5 h-3.5" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5" />
            )}
          </button>
        </div>

        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-500 uppercase tracking-wider font-bold text-[10px]">
                <th className="py-2.5 px-3 text-center">Mes</th>
                <th className="py-2.5 px-3 text-right">Saldo Inicial</th>
                <th className="py-2.5 px-3 text-right">Abono Capital</th>
                <th className="py-2.5 px-3 text-right">Intereses</th>
                <th className="py-2.5 px-3 text-right">Seguro (0.12%)</th>
                <th className="py-2.5 px-3 text-right font-black text-slate-900">Cuota Total</th>
                <th className="py-2.5 px-3 text-right">Saldo Final</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(showFullSchedule
                ? pricing.amortization_schedule
                : pricing.amortization_schedule.slice(0, 6)
              ).map((q: PaymentPeriodQuota) => (
                <tr key={q.period} className="hover:bg-slate-50/50 transition font-mono">
                  <td className="py-2.5 px-3 text-center font-bold text-slate-500">{q.period}</td>
                  <td className="py-2.5 px-3 text-right text-slate-600">
                    {formatCurrency(q.beginning_balance)}
                  </td>
                  <td className="py-2.5 px-3 text-right font-semibold text-emerald-700">
                    {formatCurrency(q.principal_amortization)}
                  </td>
                  <td className="py-2.5 px-3 text-right text-amber-600">
                    {formatCurrency(q.interest_payment)}
                  </td>
                  <td className="py-2.5 px-3 text-right text-slate-400">
                    {formatCurrency(q.insurance_payment)}
                  </td>
                  <td className="py-2.5 px-3 text-right font-black text-slate-900 bg-slate-50/40">
                    {formatCurrency(q.total_quota)}
                  </td>
                  <td className="py-2.5 px-3 text-right font-semibold text-slate-700">
                    {formatCurrency(q.ending_balance)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!showFullSchedule && pricing.amortization_schedule.length > 6 && (
            <div className="p-2.5 bg-slate-50 text-center text-slate-500 text-[11px] font-semibold border-t border-slate-200">
              Mostrando las primeras 6 cuotas de {pricing.amortization_schedule.length}. Hacé clic en &quot;Ver Tabla Completa&quot; para inspeccionar todos los meses.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
