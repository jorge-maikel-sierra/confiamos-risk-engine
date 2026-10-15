"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Inbox,
  ArrowRight,
  RefreshCw,
  Search,
  Building2,
  DollarSign,
  Calendar,
  AlertTriangle,
} from "lucide-react";
import { fetchUnderwritings } from "@/lib/api";
import { UnderwritingRecord } from "@/types/underwriting";
import { VerdictBadge } from "@/components/VerdictBadge";
import { formatCurrency, formatRatio } from "@/lib/utils";

export default function UnderwritingsInboxPage() {
  const [records, setRecords] = useState<UnderwritingRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFilter, setSelectedFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  const loadData = async (statusFilter?: string) => {
    setLoading(true);
    setError(null);
    try {
      const filterParam = statusFilter === "ALL" ? undefined : statusFilter;
      const data = await fetchUnderwritings(filterParam);
      setRecords(data.items);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "No se pudo conectar con el motor de riesgo (FastAPI)."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData(selectedFilter);
  }, [selectedFilter]);

  const filteredRecords = records.filter((r) => {
    const q = searchQuery.toLowerCase();
    return (
      r.business_name.toLowerCase().includes(q) ||
      r.application_id.toLowerCase().includes(q) ||
      r.associated_id.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">
            Bandeja de Créditos Comerciales
          </h1>
          <p className="text-sm text-slate-500 font-medium mt-1">
            Gestión y suscripción crediticia para asociados de Cooperativa Confiamos
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => loadData(selectedFilter)}
            disabled={loading}
            className="p-2 text-slate-600 hover:text-blue-600 hover:bg-slate-100 rounded-lg border border-slate-200 transition"
            title="Actualizar bandeja"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
          <Link
            href="/underwritings/new"
            className="inline-flex items-center justify-center px-4 py-2 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm transition"
          >
            + Nueva Solicitud
          </Link>
        </div>
      </div>

      {/* Filtros por pestaña y buscador */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-2 bg-white rounded-xl border border-slate-200">
        <div className="flex flex-wrap gap-1">
          {[
            { id: "ALL", label: "Todas" },
            { id: "PENDING_HUMAN_REVIEW", label: "Pendientes Comité" },
            { id: "HUMAN_APPROVED", label: "Aprobadas" },
            { id: "HUMAN_REJECTED", label: "Rechazadas" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setSelectedFilter(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                selectedFilter === tab.id
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Buscar empresa o ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full text-xs pl-9 pr-3 py-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
          />
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-bold">Error de Conexión</h4>
            <p className="text-xs text-rose-700 mt-0.5">{error}</p>
            <p className="text-[11px] text-rose-600 mt-2 font-medium">
              Verificá que el backend de FastAPI esté iniciado en http://localhost:8000.
            </p>
          </div>
        </div>
      )}

      {loading ? (
        <div className="py-20 text-center text-slate-400">
          <RefreshCw className="w-8 h-8 mx-auto animate-spin mb-3 text-blue-600" />
          <p className="text-sm font-medium">Cargando solicitudes de crédito...</p>
        </div>
      ) : filteredRecords.length === 0 ? (
        <div className="py-16 text-center bg-white rounded-2xl border border-slate-200 shadow-sm">
          <Inbox className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <h3 className="text-base font-bold text-slate-700">No se encontraron solicitudes</h3>
          <p className="text-xs text-slate-500 mt-1">
            {searchQuery
              ? "No hay resultados para tu criterio de búsqueda."
              : "No hay créditos radicados bajo este filtro de estado."}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredRecords.map((item) => {
            const dscr = item.metrics?.dscr;
            const anomalyCount = item.metrics?.anomaly_flags.length || 0;

            return (
              <div
                key={item.application_id}
                className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm hover:shadow-md transition flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-[11px] font-mono font-bold text-slate-400">
                      {item.application_id}
                    </span>
                    <VerdictBadge
                      recommendation={item.ai_verdict?.recommendation}
                      step={item.current_step}
                      isCompleted={item.is_completed}
                    />
                  </div>

                  <h3 className="text-base font-bold text-slate-900 tracking-tight flex items-center gap-1.5 line-clamp-1">
                    <Building2 className="w-4 h-4 text-blue-600 flex-shrink-0" />
                    {item.business_name}
                  </h3>
                  <span className="text-xs text-slate-400 font-medium">
                    Asociado: {item.associated_id}
                  </span>

                  <div className="mt-4 pt-3 border-t border-slate-100 grid grid-cols-2 gap-3 text-xs">
                    <div>
                      <span className="text-slate-400 block font-medium">Cobertura DSCR</span>
                      <span
                        className={`text-sm font-extrabold ${
                          dscr && dscr >= 1.25
                            ? "text-emerald-600"
                            : dscr && dscr >= 1.0
                            ? "text-amber-600"
                            : "text-rose-600"
                        }`}
                      >
                        {formatRatio(dscr)}
                      </span>
                    </div>

                    <div>
                      <span className="text-slate-400 block font-medium">Banderas Rojas</span>
                      <span
                        className={`text-sm font-extrabold ${
                          anomalyCount > 0 ? "text-rose-600" : "text-emerald-600"
                        }`}
                      >
                        {anomalyCount > 0 ? `${anomalyCount} Alertas` : "Ninguna"}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="mt-5 pt-3 border-t border-slate-100 flex items-center justify-between">
                  <span className="text-[11px] text-slate-400 font-medium">
                    {item.is_completed ? "Dictamen Finalizado" : "En Espera de Comité"}
                  </span>
                  <Link
                    href={`/underwritings/${encodeURIComponent(item.application_id)}`}
                    className="inline-flex items-center gap-1 text-xs font-bold text-blue-600 hover:text-blue-800 transition"
                  >
                    <span>Analizar Expediente</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
