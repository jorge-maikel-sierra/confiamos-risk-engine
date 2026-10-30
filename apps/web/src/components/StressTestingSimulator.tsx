"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  Flame,
  Percent,
  RefreshCw,
  Sliders,
  TrendingDown,
  TrendingUp,
  ShieldCheck,
  ShieldAlert,
} from "lucide-react";
import { fetchStressTestAnalysis, runStressTestSimulation } from "@/lib/api";
import {
  RiskRatingCategory,
  ScenarioStressResult,
  StressTestingAnalysis,
} from "@/types/underwriting";
import { formatCurrency, formatRatio } from "@/lib/utils";

interface StressTestingSimulatorProps {
  applicationId: string;
}

const RATING_COLORS: Record<RiskRatingCategory, { bg: string; text: string; border: string }> = {
  A: { bg: "bg-emerald-50", text: "text-emerald-700", border: "border-emerald-200" },
  B: { bg: "bg-blue-50", text: "text-blue-700", border: "border-blue-200" },
  C: { bg: "bg-amber-50", text: "text-amber-700", border: "border-amber-200" },
  D: { bg: "bg-orange-50", text: "text-orange-700", border: "border-orange-200" },
  E: { bg: "bg-rose-50", text: "text-rose-700", border: "border-rose-200" },
};

export function StressTestingSimulator({ applicationId }: StressTestingSimulatorProps) {
  const [analysis, setAnalysis] = useState<StressTestingAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [simulating, setSimulating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sliders para simulación custom
  const [salesShock, setSalesShock] = useState<number>(20); // 20%
  const [opexShock, setOpexShock] = useState<number>(10); // 10%
  const [rateShockBps, setRateShockBps] = useState<number>(300); // 300 bps (+3.0%)

  const loadAnalysis = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchStressTestAnalysis(applicationId);
      setAnalysis(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al cargar análisis de estrés");
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => {
    loadAnalysis();
  }, [loadAnalysis]);

  const handleSimulateCustom = async () => {
    try {
      setSimulating(true);
      setError(null);
      const updated = await runStressTestSimulation(applicationId, {
        sales_shock_pct: salesShock / 100.0,
        opex_shock_pct: opexShock / 100.0,
        interest_rate_shock_bps: rateShockBps,
      });
      setAnalysis(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al simular escenario personalizado");
    } finally {
      setSimulating(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center shadow-sm">
        <RefreshCw className="w-7 h-7 mx-auto animate-spin text-blue-600 mb-2" />
        <p className="text-xs font-semibold text-slate-500">
          Computando matriz determinística de pruebas de estrés...
        </p>
      </div>
    );
  }

  if (error || !analysis) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
        <div className="flex items-center justify-between text-rose-700 bg-rose-50 border border-rose-200 p-4 rounded-xl">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 flex-shrink-0" />
            <span className="text-xs font-semibold">{error || "No se pudo obtener el análisis."}</span>
          </div>
          <button
            onClick={loadAnalysis}
            className="text-xs font-bold underline hover:text-rose-900"
          >
            Reintentar
          </button>
        </div>
      </div>
    );
  }

  const breakevenPct = (analysis.breakeven_sales_drop_pct * 100).toFixed(1);

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-6">
      {/* 1. Header con métricas clave de resiliencia */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Tarjeta de Breakeven Sales Drop */}
        <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-1 md:col-span-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
              Margen de Quiebre (DSCR = 1.0)
            </span>
            <Activity className="w-4 h-4 text-blue-600" />
          </div>
          <div className="flex items-baseline gap-2">
            <span
              className={`text-2xl font-black ${
                analysis.breakeven_tolerable ? "text-emerald-600" : "text-amber-600"
              }`}
            >
              -{breakevenPct}%
            </span>
            <span className="text-[11px] font-medium text-slate-500">en ventas</span>
          </div>
          <p className="text-[11px] text-slate-500 leading-tight">
            {analysis.breakeven_tolerable
              ? "Tolerancia adecuada: Soporta >15% de contracción antes de insolvencia."
              : "Vulnerabilidad: Una caída leve perfora la cobertura de servicio de deuda."}
          </p>
        </div>

        {/* Resumen Cualitativo de Resiliencia */}
        <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 md:col-span-2 space-y-2">
          <div className="flex items-center gap-2">
            {analysis.breakeven_tolerable ? (
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
            ) : (
              <ShieldAlert className="w-4 h-4 text-amber-600" />
            )}
            <span className="text-xs font-bold text-slate-800">
              Dictamen de Resiliencia Financiera (Norma SARO / Basilea)
            </span>
          </div>
          <p className="text-xs text-slate-600 leading-relaxed font-medium">
            {analysis.resilience_summary}
          </p>
        </div>
      </div>

      {/* 2. Controles de Simulación Interactiva (Sliders) */}
      <div className="p-5 rounded-xl bg-gradient-to-br from-slate-50 to-blue-50/30 border border-slate-200 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-blue-600" />
            <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              Simulador Interactivo de Choques (Comité de Crédito)
            </h3>
          </div>
          <button
            onClick={handleSimulateCustom}
            disabled={simulating}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 transition shadow-sm disabled:opacity-50"
          >
            {simulating ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Flame className="w-3.5 h-3.5" />
            )}
            <span>Simular Escenario</span>
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-1">
          {/* Slider 1: Caída de Ventas */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs">
              <span className="font-semibold text-slate-600">Caída de Ventas</span>
              <span className="font-bold text-rose-600">-{salesShock}%</span>
            </div>
            <input
              type="range"
              min={0}
              max={60}
              step={5}
              value={salesShock}
              onChange={(e) => setSalesShock(Number(e.target.value))}
              className="w-full accent-rose-600 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-400">
              <span>0% (Base)</span>
              <span>-30%</span>
              <span>-60%</span>
            </div>
          </div>

          {/* Slider 2: Inflación de Costos */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs">
              <span className="font-semibold text-slate-600">Alza en Costos (Opex)</span>
              <span className="font-bold text-amber-600">+{opexShock}%</span>
            </div>
            <input
              type="range"
              min={0}
              max={50}
              step={5}
              value={opexShock}
              onChange={(e) => setOpexShock(Number(e.target.value))}
              className="w-full accent-amber-600 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-400">
              <span>0% (Base)</span>
              <span>+25%</span>
              <span>+50%</span>
            </div>
          </div>

          {/* Slider 3: Subida en Tasa de Interés */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs">
              <span className="font-semibold text-slate-600">Alza de Tasa (bps)</span>
              <span className="font-bold text-indigo-600">+{rateShockBps} bps (+{(rateShockBps / 100).toFixed(1)}%)</span>
            </div>
            <input
              type="range"
              min={0}
              max={800}
              step={50}
              value={rateShockBps}
              onChange={(e) => setRateShockBps(Number(e.target.value))}
              className="w-full accent-indigo-600 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-400">
              <span>0 bps</span>
              <span>+400 bps</span>
              <span>+800 bps</span>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Matriz Comparativa de Escenarios */}
      <div className="space-y-2">
        <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
          Matriz de Sensibilidad y Migración de Calificación (Rating A–E)
        </h4>

        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold text-[11px]">
                <th className="p-3">Escenario</th>
                <th className="p-3 text-right">EBITDA Proyectado</th>
                <th className="p-3 text-right">DSCR Estresado</th>
                <th className="p-3 text-center">Migración Rating</th>
                <th className="p-3 text-right">Provisión USD</th>
                <th className="p-3 text-right">Delta Provisión</th>
                <th className="p-3 text-center">Solvencia</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {analysis.scenarios.map((scen, idx) => {
                const baseColors = RATING_COLORS[scen.base_rating] || RATING_COLORS.E;
                const stressedColors = RATING_COLORS[scen.stressed_rating] || RATING_COLORS.E;
                const hasDelta = scen.delta_provision_usd > 0;

                return (
                  <tr
                    key={idx}
                    className={`hover:bg-slate-50/80 transition ${
                      scen.scenario_type === "COMBINED_SEVERE"
                        ? "bg-rose-50/20"
                        : scen.scenario_type === "CUSTOM"
                        ? "bg-blue-50/30 font-semibold"
                        : ""
                    }`}
                  >
                    <td className="p-3">
                      <div className="font-bold text-slate-900">{scen.scenario_name}</div>
                      <div className="text-[10px] text-slate-400">{scen.description}</div>
                    </td>
                    <td
                      className={`p-3 text-right font-mono font-bold ${
                        scen.stressed_ebitda < 0 ? "text-rose-600" : "text-slate-800"
                      }`}
                    >
                      {formatCurrency(scen.stressed_ebitda)}
                    </td>
                    <td className="p-3 text-right font-mono font-bold">
                      <span
                        className={
                          scen.stressed_dscr == null
                            ? "text-slate-400"
                            : scen.stressed_dscr >= 1.25
                            ? "text-emerald-600"
                            : scen.stressed_dscr >= 1.0
                            ? "text-amber-600"
                            : "text-rose-600"
                        }
                      >
                        {formatRatio(scen.stressed_dscr)}
                      </span>
                    </td>
                    <td className="p-3 text-center">
                      <div className="inline-flex items-center gap-1.5">
                        <span
                          className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${baseColors.bg} ${baseColors.text} ${baseColors.border}`}
                        >
                          Cat {scen.base_rating}
                        </span>
                        <ArrowRight className="w-3 h-3 text-slate-400" />
                        <span
                          className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${stressedColors.bg} ${stressedColors.text} ${stressedColors.border}`}
                        >
                          Cat {scen.stressed_rating}
                        </span>
                      </div>
                    </td>
                    <td className="p-3 text-right font-mono text-slate-700">
                      {formatCurrency(scen.stressed_provision_usd)}
                    </td>
                    <td className="p-3 text-right font-mono">
                      {hasDelta ? (
                        <span className="font-bold text-rose-600">
                          +{formatCurrency(scen.delta_provision_usd)}
                        </span>
                      ) : (
                        <span className="text-slate-400">$0.00</span>
                      )}
                    </td>
                    <td className="p-3 text-center">
                      {scen.is_solvent ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                          <span>Solvente</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-rose-700">
                          <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
                          <span>Insolvente</span>
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
