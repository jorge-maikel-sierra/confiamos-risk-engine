"use client";

import { useEffect, useState } from "react";
import {
  AlertTriangle,
  Building2,
  Car,
  CheckCircle2,
  DollarSign,
  FileCheck,
  Landmark,
  Plus,
  RefreshCw,
  Scale,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Truck,
  Wrench,
  UserCheck,
} from "lucide-react";
import { fetchCollateralAnalysis, registerCollaterals } from "@/lib/api";
import {
  CollateralItem,
  CollateralItemInput,
  CollateralType,
  UnderwritingCollateralAnalysis,
} from "@/types/underwriting";
import { formatCurrency } from "@/lib/utils";

interface CollateralValuationCardProps {
  applicationId: string;
  initialAnalysis?: UnderwritingCollateralAnalysis | null;
}

const COLLATERAL_TYPE_LABELS: Record<
  CollateralType,
  { label: string; haircut: number; icon: any; isStatutory: boolean }
> = {
  CDAT_DEPOSIT: {
    label: "CDAT / Depósito Pignorado",
    haircut: 5,
    icon: Landmark,
    isStatutory: true,
  },
  FNG_GUARANTEE: {
    label: "Garantía Institucional FNG",
    haircut: 10,
    icon: ShieldCheck,
    isStatutory: true,
  },
  REAL_ESTATE_URBAN: {
    label: "Hipoteca Inmueble Urbano",
    haircut: 20,
    icon: Building2,
    isStatutory: true,
  },
  REAL_ESTATE_RURAL: {
    label: "Hipoteca Inmueble Rural / Terreno",
    haircut: 35,
    icon: Landmark,
    isStatutory: true,
  },
  VEHICLE_COMMERCIAL: {
    label: "Prenda Flota Comercial / Vehículo",
    haircut: 30,
    icon: Truck,
    isStatutory: true,
  },
  INDUSTRIAL_MACHINERY: {
    label: "Prenda Maquinaria Industrial",
    haircut: 40,
    icon: Wrench,
    isStatutory: true,
  },
  PERSONAL_GUARANTEE: {
    label: "Pagaré con Aval Solidario",
    haircut: 50,
    icon: UserCheck,
    isStatutory: false,
  },
};

const LTV_CONFIG: Record<
  string,
  { bg: string; text: string; border: string; label: string; icon: any }
> = {
  HEALTHY: {
    bg: "bg-emerald-50",
    text: "text-emerald-700",
    border: "border-emerald-200",
    label: "Saludable (<= 70%)",
    icon: ShieldCheck,
  },
  WARNING: {
    bg: "bg-amber-50",
    text: "text-amber-700",
    border: "border-amber-200",
    label: "Alerta (70% - 85%)",
    icon: AlertTriangle,
  },
  CRITICAL: {
    bg: "bg-rose-50",
    text: "text-rose-700",
    border: "border-rose-200",
    label: "Crítico (> 85%)",
    icon: ShieldAlert,
  },
  UNSECURED: {
    bg: "bg-slate-50",
    text: "text-slate-600",
    border: "border-slate-200",
    label: "A Sola Firma (Sin Garantías)",
    icon: Shield,
  },
};

export function CollateralValuationCard({
  applicationId,
  initialAnalysis,
}: CollateralValuationCardProps) {
  const [analysis, setAnalysis] = useState<UnderwritingCollateralAnalysis | null>(
    initialAnalysis || null
  );
  const [loading, setLoading] = useState(!initialAnalysis);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);

  // Formulario de nuevo colateral
  const [newType, setNewType] = useState<CollateralType>("REAL_ESTATE_URBAN");
  const [newDescription, setNewDescription] = useState("");
  const [newAppraisal, setNewAppraisal] = useState<number>(50000);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchCollateralAnalysis(applicationId);
      setAnalysis(data);
    } catch (err: any) {
      setError(err.message || "Error al cargar valuación de garantías");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!initialAnalysis) {
      loadData();
    }
  }, [applicationId]);

  const handleAddCollateral = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDescription.trim() || newAppraisal <= 0) return;

    try {
      setSaving(true);
      setError(null);

      // Colaterales existentes + nuevo
      const currentItems: CollateralItemInput[] = (analysis?.items || []).map((i) => ({
        collateral_type: i.collateral_type,
        description: i.description,
        commercial_appraisal_usd: i.commercial_appraisal_usd,
      }));

      const updatedList: CollateralItemInput[] = [
        ...currentItems,
        {
          collateral_type: newType,
          description: newDescription.trim(),
          commercial_appraisal_usd: Number(newAppraisal),
        },
      ];

      const res = await registerCollaterals(applicationId, updatedList);
      setAnalysis(res);
      setNewDescription("");
      setShowAddForm(false);
    } catch (err: any) {
      setError(err.message || "Error al registrar la garantía");
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveCollateral = async (indexToRemove: number) => {
    if (!analysis) return;
    try {
      setSaving(true);
      const updatedList: CollateralItemInput[] = analysis.items
        .filter((_, idx) => idx !== indexToRemove)
        .map((i) => ({
          collateral_type: i.collateral_type,
          description: i.description,
          commercial_appraisal_usd: i.commercial_appraisal_usd,
        }));

      const res = await registerCollaterals(applicationId, updatedList);
      setAnalysis(res);
    } catch (err: any) {
      setError(err.message || "Error al eliminar la garantía");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 bg-white rounded-2xl border border-slate-200 text-center">
        <RefreshCw className="w-6 h-6 mx-auto animate-spin mb-2 text-blue-600" />
        <p className="text-xs text-slate-500 font-medium">Calculando valuación de garantías y LTV...</p>
      </div>
    );
  }

  if (error && !analysis) {
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

  if (!analysis) return null;

  const ltvCfg = LTV_CONFIG[analysis.ltv_status] || LTV_CONFIG.UNSECURED;
  const LtvIcon = ltvCfg.icon;

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden space-y-6 p-6">
      {/* 1. Indicadores Principales de LTV y Cobertura */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Loan to Value (LTV) */}
        <div className={`p-4 rounded-xl border ${ltvCfg.border} ${ltvCfg.bg}`}>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Loan-to-Value (LTV)
            </span>
            <LtvIcon className={`w-4 h-4 ${ltvCfg.text}`} />
          </div>
          <div className="flex items-baseline gap-2">
            <span className={`text-2xl font-black ${ltvCfg.text}`}>
              {analysis.ltv_percentage !== null ? `${analysis.ltv_percentage.toFixed(1)}%` : "N/A"}
            </span>
            <span className="text-xs font-semibold text-slate-500">Monto / Avalúo</span>
          </div>
          <p className={`text-[11px] font-bold mt-1 ${ltvCfg.text}`}>{ltvCfg.label}</p>
        </div>

        {/* Garantías Admisibles vs Solicitado */}
        <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/70">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Valor Admisible Neto
            </span>
            <Scale className="w-4 h-4 text-slate-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-black text-slate-900">
              {formatCurrency(analysis.total_admissible_usd)}
            </span>
          </div>
          <p className="text-[11px] font-medium text-slate-500 mt-1">
            Avalúo Bruto: {formatCurrency(analysis.total_appraisal_usd)}
          </p>
        </div>

        {/* Cobertura CCR y EAD Residual */}
        <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/70">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Cobertura Admisible (CCR)
            </span>
            <ShieldCheck className="w-4 h-4 text-blue-600" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-black text-blue-600">
              {analysis.collateral_coverage_ratio.toFixed(1)}%
            </span>
          </div>
          <p className="text-[11px] font-medium text-slate-500 mt-1">
            EAD Residual Neta: {formatCurrency(analysis.net_exposure_at_default_usd)}
          </p>
        </div>

        {/* Alivio Patrimonial de Provisión */}
        <div className="p-4 rounded-xl border border-emerald-200 bg-emerald-50/60">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-800">
              Alivio de Capital Liberado
            </span>
            <DollarSign className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-black text-emerald-700">
              {formatCurrency(analysis.capital_relief_usd)}
            </span>
          </div>
          <p className="text-[11px] font-semibold text-emerald-800 mt-1">
            Provisión Neta: {formatCurrency(analysis.net_provision_usd)} (Bruta:{" "}
            {formatCurrency(analysis.gross_provision_usd)})
          </p>
        </div>
      </div>

      {/* 2. Dictamen Normativo */}
      <div
        className={`p-4 rounded-xl border text-xs leading-relaxed ${
          analysis.is_fully_secured
            ? "bg-emerald-50/70 border-emerald-200 text-emerald-900"
            : analysis.ltv_status === "CRITICAL"
            ? "bg-rose-50/70 border-rose-200 text-rose-900"
            : "bg-blue-50/70 border-blue-200 text-blue-900"
        }`}
      >
        <div className="flex items-center gap-2 font-bold mb-1">
          <FileCheck className="w-4 h-4 flex-shrink-0" />
          <span>Dictamen de Idoneidad y Cobertura de Segundas Fuentes de Pago:</span>
        </div>
        <p className="ml-6 font-medium">{analysis.recommendation_notes}</p>
      </div>

      {/* 3. Tabla de Bienes y Garantías Registradas */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
            <Building2 className="w-4 h-4 text-slate-500" />
            <span>Colaterales Aportados y Ponderación de Haircuts ({analysis.items.length})</span>
          </h3>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-blue-600 bg-blue-50 hover:bg-blue-100 transition border border-blue-200"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>{showAddForm ? "Cancelar" : "Aportar Garantía"}</span>
          </button>
        </div>

        {/* Formulario Modal Inline para Agregar Colateral */}
        {showAddForm && (
          <form
            onSubmit={handleAddCollateral}
            className="mb-4 p-4 bg-slate-50 rounded-xl border border-slate-300 space-y-3"
          >
            <div className="text-xs font-bold text-slate-800">Radicar Nuevo Colateral al Expediente</div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                  Tipo de Colateral Normativo
                </label>
                <select
                  value={newType}
                  onChange={(e) => setNewType(e.target.value as CollateralType)}
                  className="w-full text-xs p-2 bg-white rounded-lg border border-slate-300 font-medium focus:ring-2 focus:ring-blue-500 outline-none"
                >
                  {Object.entries(COLLATERAL_TYPE_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v.label} (Haircut: {v.haircut}%)
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                  Avalúo Comercial Pericial (USD)
                </label>
                <input
                  type="number"
                  min="1"
                  step="1000"
                  value={newAppraisal}
                  onChange={(e) => setNewAppraisal(Number(e.target.value))}
                  className="w-full text-xs p-2 bg-white rounded-lg border border-slate-300 font-medium focus:ring-2 focus:ring-blue-500 outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                  Descripción Pericial / Ubicación
                </label>
                <input
                  type="text"
                  placeholder="Ej. Inmueble Calle 72 # 10-34, Bogotá"
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  className="w-full text-xs p-2 bg-white rounded-lg border border-slate-300 font-medium focus:ring-2 focus:ring-blue-500 outline-none"
                  required
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowAddForm(false)}
                className="px-3 py-1.5 text-xs text-slate-600 hover:text-slate-800 font-medium"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-bold hover:bg-blue-700 transition flex items-center gap-1.5 disabled:opacity-50"
              >
                {saving && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                <span>Guardar y Valuar</span>
              </button>
            </div>
          </form>
        )}

        {analysis.items.length === 0 ? (
          <div className="p-6 bg-slate-50 rounded-xl border border-slate-200 text-center text-slate-500 text-xs">
            No se han registrado garantías reales o fiduciarias para esta solicitud de crédito.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-500 uppercase tracking-wider font-bold text-[10px]">
                  <th className="py-2.5 px-3">Tipo de Colateral</th>
                  <th className="py-2.5 px-3">Descripción</th>
                  <th className="py-2.5 px-3 text-right">Avalúo Comercial</th>
                  <th className="py-2.5 px-3 text-center">Haircut (%)</th>
                  <th className="py-2.5 px-3 text-right">Valor Admisible</th>
                  <th className="py-2.5 px-3 text-center">Estatus Normativo</th>
                  <th className="py-2.5 px-3 text-center">Acción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {analysis.items.map((item, idx) => {
                  const typeMeta =
                    COLLATERAL_TYPE_LABELS[item.collateral_type] ||
                    COLLATERAL_TYPE_LABELS.REAL_ESTATE_URBAN;
                  const IconComp = typeMeta.icon;

                  return (
                    <tr key={item.id || idx} className="hover:bg-slate-50/50 transition">
                      <td className="py-2.5 px-3 font-medium text-slate-900">
                        <div className="flex items-center gap-2">
                          <IconComp className="w-4 h-4 text-slate-400 flex-shrink-0" />
                          <span>{typeMeta.label}</span>
                        </div>
                      </td>
                      <td className="py-2.5 px-3 text-slate-600 max-w-xs truncate" title={item.description}>
                        {item.description}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono font-semibold text-slate-900">
                        {formatCurrency(item.commercial_appraisal_usd)}
                      </td>
                      <td className="py-2.5 px-3 text-center font-mono font-bold text-amber-600">
                        -{item.haircut_percentage.toFixed(0)}%
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono font-black text-emerald-700">
                        {formatCurrency(item.admissible_value_usd)}
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        {item.is_statutory_admissible ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>Deduce Provisión</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-600 border border-slate-200">
                            <span>Solo Cualitativo</span>
                          </span>
                        )}
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        <button
                          onClick={() => handleRemoveCollateral(idx)}
                          disabled={saving}
                          className="text-slate-400 hover:text-rose-600 transition text-[11px] font-bold p-1"
                          title="Eliminar garantía"
                        >
                          ✕
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
