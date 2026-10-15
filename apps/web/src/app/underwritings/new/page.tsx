"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Building2,
  Calculator,
  Loader2,
  AlertTriangle,
  Sparkles,
  Check,
} from "lucide-react";
import { createUnderwriting } from "@/lib/api";
import {
  CreateUnderwritingPayload,
  FinancialExtractionResult,
} from "@/types/underwriting";
import { DocumentDropzone } from "@/components/DocumentDropzone";

export default function NewUnderwritingPage() {
  const router = useRouter();

  const [formData, setFormData] = useState({
    associated_id: "CONF-9921",
    business_name: "Transportes y Logística Andina SAS",
    requested_amount_usd: 85000,
    term_months: 24,
    operating_cash_flow: 48000,
    annual_debt_service: 22000,
    current_assets: 110000,
    current_liabilities: 55000,
    cash_balance: 30000,
    monthly_burn_rate: 0,
    negative_balance_days: 0,
    top_client_revenue_percentage: 24,
  });

  const [autofilledFields, setAutofilledFields] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleExtracted = (extracted: FinancialExtractionResult) => {
    const updatedKeys: string[] = [];

    setFormData((prev) => {
      const next = { ...prev };
      if (extracted.operating_cash_flow > 0) {
        next.operating_cash_flow = extracted.operating_cash_flow;
        updatedKeys.push("operating_cash_flow");
      }
      if (extracted.annual_debt_service > 0) {
        next.annual_debt_service = extracted.annual_debt_service;
        updatedKeys.push("annual_debt_service");
      }
      if (extracted.current_assets > 0) {
        next.current_assets = extracted.current_assets;
        updatedKeys.push("current_assets");
      }
      if (extracted.current_liabilities > 0) {
        next.current_liabilities = extracted.current_liabilities;
        updatedKeys.push("current_liabilities");
      }
      if (extracted.cash_balance > 0) {
        next.cash_balance = extracted.cash_balance;
        updatedKeys.push("cash_balance");
      }
      if (extracted.monthly_burn_rate > 0) {
        next.monthly_burn_rate = extracted.monthly_burn_rate;
        updatedKeys.push("monthly_burn_rate");
      }
      return next;
    });

    setAutofilledFields(updatedKeys);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === "number" ? parseFloat(value) || 0 : value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const payload: CreateUnderwritingPayload = {
      associated_id: formData.associated_id,
      business_name: formData.business_name,
      requested_amount_usd: formData.requested_amount_usd,
      term_months: formData.term_months,
      financial_data: {
        operating_cash_flow: formData.operating_cash_flow,
        annual_debt_service: formData.annual_debt_service,
        current_assets: formData.current_assets,
        current_liabilities: formData.current_liabilities,
        cash_balance: formData.cash_balance,
        monthly_burn_rate: formData.monthly_burn_rate,
        negative_balance_days: formData.negative_balance_days,
        top_client_revenue_percentage: formData.top_client_revenue_percentage,
      },
    };

    try {
      const res = await createUnderwriting(payload);
      router.push(`/underwritings/${encodeURIComponent(res.application_id)}`);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Error al comunicarse con el motor de riesgo (FastAPI)."
      );
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <Link
          href="/underwritings"
          className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-blue-600 transition mb-3"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Volver a la Bandeja</span>
        </Link>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">
          Radicar Solicitud de Crédito Comercial
        </h1>
        <p className="text-sm text-slate-500 font-medium mt-1">
          Ingrese los datos contables y balances del asociado para iniciar la evaluación asistida por IA.
        </p>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-bold">Error en la Radicación</h4>
            <p className="text-xs text-rose-700 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="p-8 bg-white rounded-2xl border border-slate-200 shadow-sm space-y-6">
        {/* Datos de la Empresa y Crédito */}
        <div className="space-y-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 pb-2 border-b border-slate-100 flex items-center gap-2">
            <Building2 className="w-4 h-4 text-blue-600" />
            1. Identificación y Monto Solicitado
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Nombre de la Empresa o Razón Social *
              </label>
              <input
                type="text"
                name="business_name"
                required
                value={formData.business_name}
                onChange={handleChange}
                className="w-full text-xs rounded-xl border border-slate-200 p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Código de Asociado (Cooperativa) *
              </label>
              <input
                type="text"
                name="associated_id"
                required
                value={formData.associated_id}
                onChange={handleChange}
                className="w-full text-xs rounded-xl border border-slate-200 p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Monto Solicitado (USD) *
              </label>
              <input
                type="number"
                name="requested_amount_usd"
                required
                min={1000}
                value={formData.requested_amount_usd}
                onChange={handleChange}
                className="w-full text-xs rounded-xl border border-slate-200 p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Plazo Solicitado (Meses) *
              </label>
              <input
                type="number"
                name="term_months"
                required
                min={1}
                max={120}
                value={formData.term_months}
                onChange={handleChange}
                className="w-full text-xs rounded-xl border border-slate-200 p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
              />
            </div>
          </div>
        </div>

        {/* Ingesta Documental Inteligente (SPEC-08) */}
        <div className="space-y-3 pt-4 border-t border-slate-100">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-blue-600" />
              2. Ingesta Inteligente de Estados Financieros (Opcional)
            </h3>
            <span className="text-[11px] font-medium text-slate-400">
              PDF o Excel (.xlsx, .xls)
            </span>
          </div>
          <p className="text-xs text-slate-500">
            Cargue su balance general o extracto bancario para precompletar automáticamente las cifras contables inferiores.
          </p>
          <DocumentDropzone onExtracted={handleExtracted} />
        </div>

        {/* Indicadores Financieros de Entrada */}
        <div className="space-y-4 pt-4 border-t border-slate-100">
          <div className="flex items-center justify-between pb-2 border-b border-slate-100">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <Calculator className="w-4 h-4 text-emerald-600" />
              3. Balances Contables y Cifras Validadas
            </h3>
            {autofilledFields.length > 0 && (
              <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                <Check className="w-3 h-3 text-emerald-600" />
                {autofilledFields.length} campos pre-cargados
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="flex items-center justify-between text-xs font-semibold text-slate-700 mb-1">
                <span>Flujo de Caja Operativo Anual (USD) *</span>
                {autofilledFields.includes("operating_cash_flow") && (
                  <span className="text-[10px] font-bold text-emerald-700 bg-emerald-100 px-1.5 py-0.2 rounded">
                    Auto-extraído
                  </span>
                )}
              </label>
              <input
                type="number"
                name="operating_cash_flow"
                required
                value={formData.operating_cash_flow}
                onChange={handleChange}
                className={`w-full text-xs rounded-xl border p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 transition ${
                  autofilledFields.includes("operating_cash_flow")
                    ? "border-emerald-300 bg-emerald-50/20"
                    : "border-slate-200"
                }`}
              />
            </div>

            <div>
              <label className="flex items-center justify-between text-xs font-semibold text-slate-700 mb-1">
                <span>Servicio de Deuda Anual Existente (USD) *</span>
                {autofilledFields.includes("annual_debt_service") && (
                  <span className="text-[10px] font-bold text-emerald-700 bg-emerald-100 px-1.5 py-0.2 rounded">
                    Auto-extraído
                  </span>
                )}
              </label>
              <input
                type="number"
                name="annual_debt_service"
                required
                value={formData.annual_debt_service}
                onChange={handleChange}
                className={`w-full text-xs rounded-xl border p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 transition ${
                  autofilledFields.includes("annual_debt_service")
                    ? "border-emerald-300 bg-emerald-50/20"
                    : "border-slate-200"
                }`}
              />
            </div>

            <div>
              <label className="flex items-center justify-between text-xs font-semibold text-slate-700 mb-1">
                <span>Total Activos Corrientes (USD) *</span>
                {autofilledFields.includes("current_assets") && (
                  <span className="text-[10px] font-bold text-emerald-700 bg-emerald-100 px-1.5 py-0.2 rounded">
                    Auto-extraído
                  </span>
                )}
              </label>
              <input
                type="number"
                name="current_assets"
                required
                value={formData.current_assets}
                onChange={handleChange}
                className={`w-full text-xs rounded-xl border p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 transition ${
                  autofilledFields.includes("current_assets")
                    ? "border-emerald-300 bg-emerald-50/20"
                    : "border-slate-200"
                }`}
              />
            </div>

            <div>
              <label className="flex items-center justify-between text-xs font-semibold text-slate-700 mb-1">
                <span>Total Pasivos Corrientes (USD) *</span>
                {autofilledFields.includes("current_liabilities") && (
                  <span className="text-[10px] font-bold text-emerald-700 bg-emerald-100 px-1.5 py-0.2 rounded">
                    Auto-extraído
                  </span>
                )}
              </label>
              <input
                type="number"
                name="current_liabilities"
                required
                value={formData.current_liabilities}
                onChange={handleChange}
                className={`w-full text-xs rounded-xl border p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 transition ${
                  autofilledFields.includes("current_liabilities")
                    ? "border-emerald-300 bg-emerald-50/20"
                    : "border-slate-200"
                }`}
              />
            </div>

            <div>
              <label className="flex items-center justify-between text-xs font-semibold text-slate-700 mb-1">
                <span>Saldo de Caja y Bancos (USD) *</span>
                {autofilledFields.includes("cash_balance") && (
                  <span className="text-[10px] font-bold text-emerald-700 bg-emerald-100 px-1.5 py-0.2 rounded">
                    Auto-extraído
                  </span>
                )}
              </label>
              <input
                type="number"
                name="cash_balance"
                required
                value={formData.cash_balance}
                onChange={handleChange}
                className={`w-full text-xs rounded-xl border p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 transition ${
                  autofilledFields.includes("cash_balance")
                    ? "border-emerald-300 bg-emerald-50/20"
                    : "border-slate-200"
                }`}
              />
            </div>

            <div>
              <label className="flex items-center justify-between text-xs font-semibold text-slate-700 mb-1">
                <span>Tasa de Quema Mensual (Burn Rate)</span>
                {autofilledFields.includes("monthly_burn_rate") && (
                  <span className="text-[10px] font-bold text-emerald-700 bg-emerald-100 px-1.5 py-0.2 rounded">
                    Auto-extraído
                  </span>
                )}
              </label>
              <input
                type="number"
                name="monthly_burn_rate"
                value={formData.monthly_burn_rate}
                onChange={handleChange}
                className={`w-full text-xs rounded-xl border p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 transition ${
                  autofilledFields.includes("monthly_burn_rate")
                    ? "border-emerald-300 bg-emerald-50/20"
                    : "border-slate-200"
                }`}
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Días con Saldo Negativo / Sobregiro
              </label>
              <input
                type="number"
                name="negative_balance_days"
                min={0}
                value={formData.negative_balance_days}
                onChange={handleChange}
                className="w-full text-xs rounded-xl border border-slate-200 p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                % Ingresos del Mayor Cliente (%)
              </label>
              <input
                type="number"
                name="top_client_revenue_percentage"
                min={0}
                max={100}
                value={formData.top_client_revenue_percentage}
                onChange={handleChange}
                className="w-full text-xs rounded-xl border border-slate-200 p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
              />
            </div>
          </div>
        </div>

        <div className="pt-6 border-t border-slate-100 flex items-center justify-end gap-3">
          <Link
            href="/underwritings"
            className="px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition"
          >
            Cancelar
          </Link>
          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 shadow-sm transition disabled:opacity-50"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Ejecutando StateGraph en Backend...</span>
              </>
            ) : (
              <span>Radicar e Iniciar Evaluación</span>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
