"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Landmark,
  Loader2,
  Lock,
  Receipt,
  Send,
  ShieldCheck,
  FileText,
} from "lucide-react";
import {
  executeDisbursement,
  fetchDisbursementGateStatus,
  verifyCovenant,
} from "@/lib/api";
import {
  CovenantFulfillmentRecord,
  CovenantFulfillmentStatus,
  DisbursementGateStatus,
  DisbursementOrder,
} from "@/types/underwriting";

interface DisbursementGateCardProps {
  applicationId: string;
  initialOrder?: DisbursementOrder | null;
  onDisbursementExecuted?: (order: DisbursementOrder) => void;
}

export function DisbursementGateCard({
  applicationId,
  initialOrder,
  onDisbursementExecuted,
}: DisbursementGateCardProps) {
  const [gateStatus, setGateStatus] = useState<DisbursementGateStatus | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Verificación de covenant en curso
  const [activeVerifyCode, setActiveVerifyCode] = useState<string | null>(null);
  const [officerName, setOfficerName] = useState("");
  const [verifyNotes, setVerifyNotes] = useState("");
  const [verifyStatus, setVerifyStatus] = useState<CovenantFulfillmentStatus>(
    "FULFILLED"
  );
  const [verifying, setVerifying] = useState(false);

  // Formulario de ejecución de giro
  const [destBank, setDestBank] = useState("Bancolombia");
  const [destAccount, setDestAccount] = useState("");
  const [accountType, setAccountType] = useState("AHORROS");
  const [acceptTerms, setAcceptTerms] = useState(true);
  const [executing, setExecuting] = useState(false);

  const loadStatus = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDisbursementGateStatus(applicationId);
      setGateStatus(data);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Error al cargar estado de la compuerta de desembolso"
      );
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const handleVerifyCovenant = async (code: string) => {
    if (!officerName.trim()) {
      alert("Por favor ingrese el nombre o ID del oficial que verifica.");
      return;
    }
    setVerifying(true);
    setError(null);
    try {
      const updated = await verifyCovenant(applicationId, code, {
        verified_by: officerName.trim(),
        notes: verifyNotes.trim() || undefined,
        status: verifyStatus,
      });
      setGateStatus(updated);
      setActiveVerifyCode(null);
      setVerifyNotes("");
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Error al registrar verificación de la condición"
      );
    } finally {
      setVerifying(false);
    }
  };

  const handleExecuteDisbursement = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!destAccount.trim()) {
      alert("Ingrese el número de cuenta de destino.");
      return;
    }
    if (!acceptTerms) {
      alert("Debe confirmar la emisión del pagaré y cláusula aceleratoria.");
      return;
    }
    setExecuting(true);
    setError(null);
    try {
      const order = await executeDisbursement(applicationId, {
        destination_bank: destBank.trim(),
        destination_account_number: destAccount.trim(),
        account_type: accountType,
      });
      if (onDisbursementExecuted) {
        onDisbursementExecuted(order);
      }
      await loadStatus();
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Error al ejecutar el desembolso y formalizar giro"
      );
    } finally {
      setExecuting(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 bg-white rounded-2xl border border-slate-200 shadow-sm flex items-center justify-center gap-3 text-slate-500">
        <Loader2 className="w-5 h-5 animate-spin text-emerald-600" />
        <span className="text-sm font-medium">
          Evaluando compuerta de desembolso y covenants precedentes...
        </span>
      </div>
    );
  }

  const order = gateStatus?.disbursement_order || initialOrder;
  const isDisbursed = !!order;
  const isEligible = gateStatus?.is_eligible ?? false;
  const liquidation = gateStatus?.liquidation_preview;

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Encabezado Principal */}
      <div className="p-5 border-b border-slate-100 flex flex-col md:flex-row md:items-center justify-between gap-3 bg-gradient-to-r from-slate-50 to-white">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold">
            <Landmark className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-900 tracking-tight flex items-center gap-2">
              Compuerta de Desembolso, Liquidación y Pagaré Digital (SPEC-14)
            </h3>
            <p className="text-xs text-slate-500">
              Verificación estricta de covenants, deducciones estatutarias
              (Aportes 2%) y orden de giro ACH.
            </p>
          </div>
        </div>

        {/* Badge Semáforo de Estado */}
        <div>
          {isDisbursed ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              DESEMBOLSADO — CARTERA ACTIVA
            </span>
          ) : isEligible ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 animate-pulse">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              COMPUERTA ABIERTA — HABILITADO
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200">
              <Lock className="w-4 h-4 text-amber-600" />
              DESEMBOLSO BLOQUEADO
            </span>
          )}
        </div>
      </div>

      {/* Alerta de Error si ocurre */}
      {error && (
        <div className="m-5 p-4 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Vista de Desembolso Completado (Comprobante Oficial) */}
      {isDisbursed && order && (
        <div className="p-6 bg-slate-50 border-b border-slate-200">
          <div className="bg-white rounded-xl p-6 border border-emerald-200 shadow-sm relative overflow-hidden">
            <div className="absolute top-0 right-0 transform translate-x-4 -translate-y-4 w-32 h-32 bg-emerald-50 rounded-full pointer-events-none opacity-60" />
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600 block">
                  Orden de Giro Oficial Ejecutada
                </span>
                <h4 className="text-xl font-mono font-bold text-slate-900">
                  {order.order_id}
                </h4>
              </div>
              <div className="text-left sm:text-right">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                  Pagaré Digital Desmaterializado
                </span>
                <span className="text-sm font-mono font-bold text-indigo-700">
                  {order.promissory_note.note_number}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 py-4 border-b border-slate-100 text-xs">
              <div>
                <span className="text-slate-400 block">Monto Bruto:</span>
                <span className="font-semibold text-slate-800">
                  ${order.liquidation.gross_amount_usd.toLocaleString("en-US", { minimumFractionDigits: 2 })} USD
                </span>
              </div>
              <div>
                <span className="text-slate-400 block">Deducciones Solidarias:</span>
                <span className="font-semibold text-rose-600">
                  -${order.liquidation.total_deductions_usd.toLocaleString("en-US", { minimumFractionDigits: 2 })} USD
                </span>
              </div>
              <div>
                <span className="text-slate-400 block">Neto Girado a Cuenta:</span>
                <span className="font-bold text-emerald-600 text-sm">
                  ${order.liquidation.net_disbursement_usd.toLocaleString("en-US", { minimumFractionDigits: 2 })} USD
                </span>
              </div>
              <div>
                <span className="text-slate-400 block">Tasa Pactada (TEA):</span>
                <span className="font-semibold text-slate-800">
                  {order.promissory_note.applied_tea.toFixed(2)}% E.A.
                </span>
              </div>
            </div>

            <div className="pt-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-slate-600">
              <div className="flex items-center gap-2">
                <Landmark className="w-4 h-4 text-slate-400" />
                <span>
                  <strong>Destino:</strong> {order.destination_bank} • {order.account_type} {order.destination_account_number}
                </span>
              </div>
              <div className="flex items-center gap-1.5 text-slate-500">
                <Clock className="w-3.5 h-3.5" />
                <span>Fecha de giro: {new Date(order.disbursed_at).toLocaleString("es-CO")}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Motivos de Bloqueo (si no es elegible y no está desembolsado) */}
      {!isDisbursed && !isEligible && gateStatus && gateStatus.blocking_reasons.length > 0 && (
        <div className="p-5 bg-amber-50/70 border-b border-amber-200">
          <div className="flex items-start gap-3">
            <Lock className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h4 className="text-xs font-bold text-amber-900 uppercase tracking-wider">
                Condiciones Bloqueantes del Desembolso
              </h4>
              <ul className="text-xs text-amber-800 space-y-1 list-disc list-inside">
                {gateStatus.blocking_reasons.map((reason, idx) => (
                  <li key={idx}>{reason}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Sección 1: Covenants Precedentes (Checklist de Verificación) */}
      <div className="p-6 border-b border-slate-100 space-y-4">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <h4 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-indigo-600" />
              <span>Verificación de Covenants Precedentes</span>
            </h4>
            <p className="text-xs text-slate-500">
              Condiciones obligatorias pactadas en acta de comité antes del giro.
            </p>
          </div>
          {gateStatus && (
            <span className="text-xs font-bold text-slate-600 bg-slate-100 px-3 py-1 rounded-full border border-slate-200">
              {gateStatus.pending_covenants_count === 0
                ? "100% Covenants Verificados"
                : `${gateStatus.pending_covenants_count} Pendiente(s)`}
            </span>
          )}
        </div>

        {gateStatus && gateStatus.covenants.length === 0 ? (
          <div className="p-4 bg-slate-50 rounded-xl border border-dashed border-slate-200 text-xs text-slate-500 text-center">
            No se impusieron covenants o condiciones precedentes para esta solicitud.
          </div>
        ) : (
          <div className="space-y-3">
            {gateStatus?.covenants.map((cov: CovenantFulfillmentRecord) => {
              const isPending = cov.status === "PENDING";
              const isFulfilled = cov.status === "FULFILLED";
              const isWaived = cov.status === "WAIVED";

              return (
                <div
                  key={cov.code}
                  className={`p-4 rounded-xl border text-xs transition ${
                    isPending
                      ? "bg-amber-50/40 border-amber-200"
                      : isFulfilled
                      ? "bg-emerald-50/40 border-emerald-200"
                      : "bg-purple-50/40 border-purple-200"
                  }`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-slate-900 bg-white px-2 py-0.5 rounded border border-slate-200">
                          {cov.code}
                        </span>
                        <span className="text-[10px] uppercase font-bold text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                          {cov.covenant_type || "GARANTIA"}
                        </span>
                        <span className="text-slate-400">• Plazo: {cov.due_days} días</span>
                      </div>
                      <p className="text-slate-800 font-medium">{cov.description}</p>
                    </div>

                    <div className="flex items-center gap-2">
                      {isPending && (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold bg-amber-100 text-amber-800">
                          <Clock className="w-3 h-3 text-amber-600" />
                          Pendiente
                        </span>
                      )}
                      {isFulfilled && (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800">
                          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                          Verificado
                        </span>
                      )}
                      {isWaived && (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold bg-purple-100 text-purple-800">
                          <ShieldCheck className="w-3 h-3 text-purple-600" />
                          Exonerado
                        </span>
                      )}

                      {!isDisbursed && isPending && (
                        <button
                          onClick={() => {
                            setActiveVerifyCode(
                              activeVerifyCode === cov.code ? null : cov.code
                            );
                            setOfficerName("");
                            setVerifyNotes("");
                          }}
                          className="px-3 py-1 rounded-lg text-xs font-bold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 transition"
                        >
                          {activeVerifyCode === cov.code ? "Cancelar" : "Verificar"}
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Detalle si ya fue verificado */}
                  {(cov.verified_by || cov.evidence_notes) && (
                    <div className="mt-2 pt-2 border-t border-slate-200/60 flex flex-col sm:flex-row sm:items-center justify-between text-[11px] text-slate-500 gap-1">
                      <span>
                        <strong>Auditado por:</strong> {cov.verified_by || "Oficial de Cartera"}
                        {cov.evidence_notes ? ` • Notas: ${cov.evidence_notes}` : ""}
                      </span>
                      {cov.verified_at && (
                        <span>{new Date(cov.verified_at).toLocaleString("es-CO")}</span>
                      )}
                    </div>
                  )}

                  {/* Formulario de Verificación Desplegable */}
                  {activeVerifyCode === cov.code && (
                    <div className="mt-3 pt-3 border-t border-amber-200 space-y-3 bg-white p-3 rounded-lg border">
                      <h5 className="font-bold text-slate-800 text-xs">
                        Radicar Cumplimiento de Condición Precedente
                      </h5>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        <div>
                          <label className="text-[11px] font-bold text-slate-600 block mb-1">
                            Oficial Responsable:
                          </label>
                          <input
                            type="text"
                            placeholder="Ej. Ana Oficial / ID 4892"
                            value={officerName}
                            onChange={(e) => setOfficerName(e.target.value)}
                            className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="text-[11px] font-bold text-slate-600 block mb-1">
                            Dictamen:
                          </label>
                          <select
                            value={verifyStatus}
                            onChange={(e) =>
                              setVerifyStatus(
                                e.target.value as CovenantFulfillmentStatus
                              )
                            }
                            className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none bg-white"
                          >
                            <option value="FULFILLED">FULFILLED (Verificado y Aceptado)</option>
                            <option value="WAIVED">WAIVED (Exonerado por Consejo)</option>
                          </select>
                        </div>
                      </div>
                      <div>
                        <label className="text-[11px] font-bold text-slate-600 block mb-1">
                          Radicado o Evidencia Documental:
                        </label>
                        <input
                          type="text"
                          placeholder="Número de póliza, matrícula inmobiliaria o radicado de registro..."
                          value={verifyNotes}
                          onChange={(e) => setVerifyNotes(e.target.value)}
                          className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none"
                        />
                      </div>
                      <div className="flex justify-end gap-2 pt-1">
                        <button
                          type="button"
                          onClick={() => setActiveVerifyCode(null)}
                          className="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-100"
                        >
                          Cerrar
                        </button>
                        <button
                          type="button"
                          disabled={verifying}
                          onClick={() => handleVerifyCovenant(cov.code)}
                          className="px-4 py-1.5 rounded-lg text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-1.5 shadow-sm"
                        >
                          {verifying && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                          Confirmar Verificación
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Sección 2: Liquidación Cooperativa Estatutaria (Desglose de Deducciones) */}
      {liquidation && (
        <div className="p-6 border-b border-slate-100 space-y-4">
          <div className="space-y-0.5">
            <h4 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Receipt className="w-4 h-4 text-emerald-600" />
              <span>Liquidación Neta de Cartera (Estatutos Cooperativa Confiamos)</span>
            </h4>
            <p className="text-xs text-slate-500">
              Retención de aportes sociales para fortalecimiento patrimonial y auxilio solidario.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 text-xs space-y-2.5">
              <div className="flex justify-between items-center text-slate-600">
                <span>Monto Bruto Aprobado:</span>
                <span className="font-semibold text-slate-900">
                  ${liquidation.gross_amount_usd.toLocaleString("en-US", { minimumFractionDigits: 2 })} USD
                </span>
              </div>
              <div className="flex justify-between items-center text-slate-600">
                <span>Aportes Sociales Estatutarios (2.0%):</span>
                <span className="font-semibold text-rose-600">
                  -${liquidation.social_contributions_usd.toLocaleString("en-US", { minimumFractionDigits: 2 })} USD
                </span>
              </div>
              <div className="flex justify-between items-center text-slate-600">
                <span>Fondo de Solidaridad y Auxilio Mutual (Fijo):</span>
                <span className="font-semibold text-rose-600">
                  -${liquidation.solidarity_fund_usd.toLocaleString("en-US", { minimumFractionDigits: 2 })} USD
                </span>
              </div>
              <div className="flex justify-between items-center text-slate-600">
                <span>Seguro de Cartera (Mes 1):</span>
                <span className="font-semibold text-rose-600">
                  -${liquidation.insurance_first_month_usd.toLocaleString("en-US", { minimumFractionDigits: 2 })} USD
                </span>
              </div>
              <div className="pt-2 border-t border-slate-200 flex justify-between items-center font-bold text-slate-800">
                <span>Total Deducciones:</span>
                <span className="text-rose-700">
                  -${liquidation.total_deductions_usd.toLocaleString("en-US", { minimumFractionDigits: 2 })} USD
                </span>
              </div>
            </div>

            <div className="bg-gradient-to-br from-emerald-500/10 to-emerald-500/5 p-5 rounded-xl border border-emerald-300 flex flex-col justify-between">
              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-800 block">
                  Monto Neto a Desembolsar (Giro Efectivo)
                </span>
                <p className="text-3xl font-black text-emerald-700 tracking-tight mt-1">
                  ${liquidation.net_disbursement_usd.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                  <span className="text-sm font-semibold text-emerald-600 ml-1">USD</span>
                </p>
                <p className="text-xs text-emerald-800/80 mt-1 leading-relaxed">
                  Valor transferible a la cuenta del asociado una vez formalizada la orden de giro.
                </p>
              </div>
              <div className="pt-3 border-t border-emerald-200/60 text-[11px] text-emerald-800 flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-emerald-600" />
                <span>Pagaré Digital será emitido por el valor bruto capital.</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Sección 3: Estación de Formalización y Desembolso (Si aún no se ha girado) */}
      {!isDisbursed && (
        <div className="p-6 bg-slate-50/70">
          <form onSubmit={handleExecuteDisbursement} className="space-y-4">
            <div className="space-y-0.5">
              <h4 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Send className="w-4 h-4 text-emerald-600" />
                <span>Formalización de Giro y Emisión de Pagaré Digital</span>
              </h4>
              <p className="text-xs text-slate-500">
                Emisión del título valor con cláusula aceleratoria y generación de orden de transferencia ACH.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">
                  Banco Destino:
                </label>
                <input
                  type="text"
                  required
                  disabled={!isEligible}
                  value={destBank}
                  onChange={(e) => setDestBank(e.target.value)}
                  placeholder="Ej. Bancolombia, Davivienda..."
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:bg-slate-100 disabled:text-slate-400"
                />
              </div>
              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">
                  Número de Cuenta:
                </label>
                <input
                  type="text"
                  required
                  disabled={!isEligible}
                  value={destAccount}
                  onChange={(e) => setDestAccount(e.target.value)}
                  placeholder="Ej. 100-293847-01"
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:bg-slate-100 disabled:text-slate-400"
                />
              </div>
              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">
                  Tipo de Cuenta:
                </label>
                <select
                  disabled={!isEligible}
                  value={accountType}
                  onChange={(e) => setAccountType(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs focus:ring-2 focus:ring-emerald-500 focus:outline-none bg-white disabled:bg-slate-100 disabled:text-slate-400"
                >
                  <option value="AHORROS">Cuenta de Ahorros</option>
                  <option value="CORRIENTE">Cuenta Corriente</option>
                </select>
              </div>
            </div>

            <div className="flex items-center gap-2 pt-1">
              <input
                type="checkbox"
                id="acceptTerms"
                disabled={!isEligible}
                checked={acceptTerms}
                onChange={(e) => setAcceptTerms(e.target.checked)}
                className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
              />
              <label
                htmlFor="acceptTerms"
                className="text-xs text-slate-600 select-none cursor-pointer"
              >
                Certifico el cumplimiento de condiciones, expedición del <strong>Pagaré Desmaterializado</strong> y aceptación de la cláusula de aceleración por mora.
              </label>
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="submit"
                disabled={!isEligible || executing}
                className="px-6 py-2.5 rounded-xl text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 shadow-md shadow-emerald-600/20 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition"
              >
                {executing ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <CheckCircle2 className="w-4 h-4" />
                )}
                <span>Emitir Pagaré y Desembolsar</span>
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
