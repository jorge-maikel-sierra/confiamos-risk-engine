"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Building2,
  Calendar,
  DollarSign,
  ShieldAlert,
  Bot,
  HelpCircle,
  TrendingUp,
  AlertTriangle,
  RefreshCw,
} from "lucide-react";
import { fetchUnderwritingById } from "@/lib/api";
import { UnderwritingRecord } from "@/types/underwriting";
import { MetricCard } from "@/components/MetricCard";
import { VerdictBadge } from "@/components/VerdictBadge";
import { AnomalyAlertList } from "@/components/AnomalyAlertList";
import { HumanReviewForm } from "@/components/HumanReviewForm";
import { formatCurrency, formatRatio } from "@/lib/utils";

export default function UnderwritingDetailPage() {
  const params = useParams();
  const id = params?.id as string;

  const [record, setRecord] = useState<UnderwritingRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadRecord = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchUnderwritingById(id);
      setRecord(data);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "No se pudo cargar el expediente crediticio."
      );
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadRecord();
  }, [loadRecord]);

  if (loading) {
    return (
      <div className="py-24 text-center">
        <RefreshCw className="w-8 h-8 mx-auto animate-spin mb-3 text-blue-600" />
        <p className="text-sm font-semibold text-slate-600">Cargando expediente crediticio...</p>
      </div>
    );
  }

  if (error || !record) {
    return (
      <div className="max-w-2xl mx-auto py-12">
        <div className="p-6 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-center">
          <AlertTriangle className="w-10 h-10 text-rose-600 mx-auto mb-3" />
          <h2 className="text-lg font-bold">Error al Cargar la Solicitud</h2>
          <p className="text-xs text-rose-700 mt-1">{error || "Expediente no encontrado."}</p>
          <div className="mt-6">
            <Link
              href="/underwritings"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 transition"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Volver a la Bandeja</span>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const metrics = record.metrics;
  const dscr = metrics?.dscr;
  const currentRatio = metrics?.current_ratio;
  const runway = metrics?.runway_months;
  const verdict = record.ai_verdict;

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      {/* Header con botón de regreso y acciones */}
      <div>
        <Link
          href="/underwritings"
          className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-blue-600 transition mb-3"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Volver a la Bandeja de Créditos</span>
        </Link>

        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-6 bg-white rounded-2xl border border-slate-200 shadow-sm">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="text-xs font-mono font-bold text-slate-400">
                {record.application_id}
              </span>
              <VerdictBadge
                recommendation={verdict?.recommendation}
                step={record.current_step}
                isCompleted={record.is_completed}
              />
            </div>
            <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2">
              <Building2 className="w-6 h-6 text-blue-600 flex-shrink-0" />
              {record.business_name}
            </h1>
            <p className="text-xs text-slate-500 font-medium mt-1">
              Asociado Comercial: <span className="font-semibold text-slate-700">{record.associated_id}</span>
            </p>
          </div>

          <div className="flex items-center gap-4 border-t md:border-t-0 pt-3 md:pt-0 border-slate-100">
            <div className="text-right">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Estado del Workflow</span>
              <span className="text-sm font-bold text-slate-800">{record.current_step}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Ratios Financieros Determinísticos (Matemática Pura) */}
      <section className="space-y-3">
        <h2 className="text-base font-bold text-slate-900 tracking-tight flex items-center gap-2">
          <span>1. Indicadores Determinísticos de Solvencia y Cobertura</span>
          <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
            Cálculo Exacto en Python
          </span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <MetricCard
            label="Ratio de Cobertura (DSCR)"
            value={formatRatio(dscr)}
            description="Flujo operativo / Servicio de deuda anual. Mínimo 1.25x para aprobación directa."
            status={
              dscr == null ? "neutral" : dscr >= 1.25 ? "success" : dscr >= 1.0 ? "warning" : "danger"
            }
          />
          <MetricCard
            label="Liquidez Corriente"
            value={formatRatio(currentRatio)}
            description="Activo corriente / Pasivo corriente. Capacidad de responder a compromisos a corto plazo."
            status={
              currentRatio == null ? "neutral" : currentRatio >= 1.2 ? "success" : currentRatio >= 1.0 ? "warning" : "danger"
            }
          />
          <MetricCard
            label="Runway de Tesorería"
            value={runway != null ? `${runway} Meses` : "Superávit (Sin Burn)"}
            description="Meses de operación con saldo de caja disponible ante un escenario de quema mensual."
            status={
              runway == null ? "success" : runway >= 6 ? "success" : runway >= 3 ? "warning" : "danger"
            }
          />
        </div>
      </section>

      {/* Banderas de Anomalías Detectadas */}
      <section className="space-y-3">
        <h2 className="text-base font-bold text-slate-900 tracking-tight">
          2. Detección de Banderas Rojas y Riesgos Operativos
        </h2>
        <AnomalyAlertList flags={metrics?.anomaly_flags || []} />
      </section>

      {/* Dictamen Cualitativo de Gemini 1.5 Flash */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <Bot className="w-5 h-5 text-indigo-600" />
            <span>3. Auditoría Cualitativa Inteligente (Google Gemini)</span>
          </h2>
          {verdict && (
            <span className="text-xs font-bold text-indigo-700 bg-indigo-50 px-3 py-1 rounded-full border border-indigo-200">
              Confianza del Modelo: {(verdict.confidence_score * 100).toFixed(0)}%
            </span>
          )}
        </div>

        {verdict ? (
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-6">
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
                Resumen Ejecutivo de Riesgo
              </h4>
              <p className="text-sm text-slate-700 leading-relaxed font-medium bg-slate-50 p-4 rounded-xl border border-slate-100">
                {verdict.executive_summary}
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-600 mb-3 flex items-center gap-1.5">
                  <TrendingUp className="w-4 h-4" />
                  Fortalezas Identificadas
                </h4>
                <ul className="space-y-2">
                  {verdict.key_strengths.map((str, idx) => (
                    <li key={idx} className="text-xs text-slate-700 flex items-start gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-1.5 flex-shrink-0" />
                      <span>{str}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-rose-600 mb-3 flex items-center gap-1.5">
                  <ShieldAlert className="w-4 h-4" />
                  Riesgos Observados
                </h4>
                <ul className="space-y-2">
                  {verdict.identified_risks.map((risk, idx) => (
                    <li key={idx} className="text-xs text-slate-700 flex items-start gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-rose-500 mt-1.5 flex-shrink-0" />
                      <span>{risk}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-100">
              <h4 className="text-xs font-bold uppercase tracking-wider text-blue-600 mb-3 flex items-center gap-1.5">
                <HelpCircle className="w-4 h-4" />
                Cuestionario de Due Diligence Recomendado para el Oficial
              </h4>
              <div className="space-y-2">
                {verdict.due_diligence_questions.map((q, idx) => (
                  <div
                    key={idx}
                    className="p-3 bg-blue-50/50 border border-blue-100 rounded-xl text-xs text-blue-900 font-medium"
                  >
                    <span className="font-bold text-blue-700 mr-2">P{idx + 1}:</span>
                    {q}
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="p-6 bg-white rounded-2xl border border-slate-200 text-center text-slate-400 text-xs">
            No se dispone de dictamen de IA para esta solicitud.
          </div>
        )}
      </section>

      {/* Formulario de Decisión Humana (Human-in-the-loop) */}
      <section className="space-y-3">
        <h2 className="text-base font-bold text-slate-900 tracking-tight">
          4. Resolución Definitiva de Comité
        </h2>
        <HumanReviewForm
          applicationId={record.application_id}
          isCompleted={record.is_completed}
          humanApproved={record.human_approved}
          humanNotes={record.human_notes}
          onReviewSubmitted={(updated) => setRecord(updated)}
        />
      </section>
    </div>
  );
}
