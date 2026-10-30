"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Users,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  XCircle,
  FileText,
  Clock,
  Plus,
  Trash2,
  Loader2,
  Award,
} from "lucide-react";
import { castCommitteeVote, fetchCommitteeResolution } from "@/lib/api";
import {
  ApprovalAuthorityLevel,
  CommitteeMemberRole,
  CommitteeResolution,
  CommitteeVoteType,
  CreditCovenant,
} from "@/types/underwriting";

interface CommitteeGovernanceCardProps {
  applicationId: string;
  initialResolution?: CommitteeResolution | null;
  onResolutionUpdated?: (resolution: CommitteeResolution) => void;
}

const ROLE_LABELS: Record<CommitteeMemberRole, string> = {
  RISK_OFFICER: "Oficial de Riesgos",
  CREDIT_MANAGER: "Gerente de Crédito",
  OPERATIONS_DIRECTOR: "Director de Operaciones",
  BOARD_DIRECTOR: "Vocal del Consejo de Administración",
};

const LEVEL_CONFIG: Record<
  ApprovalAuthorityLevel,
  { name: string; badgeClass: string; desc: string }
> = {
  LEVEL_1_OFFICER: {
    name: "Nivel 1 — Oficial Individual",
    badgeClass: "bg-emerald-50 text-emerald-700 border-emerald-200",
    desc: "Monto hasta $15,000 USD, calificación A/B y LTV saludable.",
  },
  LEVEL_2_MANAGER: {
    name: "Nivel 2 — Gerencia de Riesgo",
    badgeClass: "bg-blue-50 text-blue-700 border-blue-200",
    desc: "Monto hasta $40,000 USD o colaterales en advertencia.",
  },
  LEVEL_3_COMMITTEE: {
    name: "Nivel 3 — Comité Colegiado",
    badgeClass: "bg-amber-50 text-amber-700 border-amber-200",
    desc: "Monto hasta $100,000 USD o calificación C. Quórum estatutario de 3 miembros.",
  },
  LEVEL_4_BOARD: {
    name: "Nivel 4 — Consejo de Administración",
    badgeClass: "bg-purple-50 text-purple-700 border-purple-200",
    desc: "Monto > $100,000 USD, calificación D/E o alerta de usura.",
  },
};

export function CommitteeGovernanceCard({
  applicationId,
  initialResolution,
  onResolutionUpdated,
}: CommitteeGovernanceCardProps) {
  const [resolution, setResolution] = useState<CommitteeResolution | null>(
    initialResolution || null
  );
  const [loading, setLoading] = useState(!initialResolution);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Formulario de emisión de voto
  const [voterName, setVoterName] = useState("");
  const [role, setRole] = useState<CommitteeMemberRole>("RISK_OFFICER");
  const [vote, setVote] = useState<CommitteeVoteType>("APPROVE");
  const [notes, setNotes] = useState("");
  const [covenants, setCovenants] = useState<CreditCovenant[]>([]);

  // Campos para nuevo covenant
  const [newCovCode, setNewCovCode] = useState("");
  const [newCovDesc, setNewCovDesc] = useState("");
  const [newCovType, setNewCovType] = useState("GARANTIA");
  const [newCovDays, setNewCovDays] = useState(30);

  const loadResolution = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchCommitteeResolution(applicationId);
      setResolution(res);
      if (onResolutionUpdated) onResolutionUpdated(res);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Error al cargar la resolución de comité."
      );
    } finally {
      setLoading(false);
    }
  }, [applicationId, onResolutionUpdated]);

  useEffect(() => {
    if (!initialResolution) {
      loadResolution();
    }
  }, [initialResolution, loadResolution]);

  const handleAddCovenant = () => {
    if (!newCovCode.trim() || !newCovDesc.trim()) return;
    const item: CreditCovenant = {
      code: newCovCode.trim().toUpperCase(),
      description: newCovDesc.trim(),
      covenant_type: newCovType,
      due_days: Number(newCovDays) || 30,
    };
    setCovenants([...covenants, item]);
    setNewCovCode("");
    setNewCovDesc("");
  };

  const handleRemoveCovenant = (index: number) => {
    setCovenants(covenants.filter((_, i) => i !== index));
  };

  const handleCastVote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!voterName.trim()) {
      setError("Ingrese el nombre completo del miembro votante.");
      return;
    }
    if (!notes.trim() || notes.trim().length < 5) {
      setError("Debe proporcionar una justificación técnica fundamentada (mínimo 5 caracteres).");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const voterId = `USR-${role.toLowerCase().replace("_", "-")}-${voterName.toLowerCase().replace(/\s+/g, "")}`;
      const updated = await castCommitteeVote(applicationId, {
        voter_id: voterId,
        voter_name: voterName.trim(),
        role,
        vote,
        notes: notes.trim(),
        covenants: vote === "CONDITION" || covenants.length > 0 ? covenants : [],
      });

      setResolution(updated);
      setNotes("");
      setCovenants([]);
      if (onResolutionUpdated) onResolutionUpdated(updated);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Error al registrar el voto en la sesión de comité."
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 bg-white rounded-2xl border border-slate-200 text-center">
        <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-600" />
        <p className="text-xs font-semibold text-slate-500">
          Determinando competencia estatutaria y estado de comité...
        </p>
      </div>
    );
  }

  if (!resolution) {
    return null;
  }

  const levelInfo = LEVEL_CONFIG[resolution.governance_level] || {
    name: resolution.governance_level,
    badgeClass: "bg-slate-100 text-slate-700 border-slate-200",
    desc: "Instancia decisoria estatutaria.",
  };

  const isFinal = resolution.is_final;
  const isApproved =
    resolution.status === "APPROVED_BY_COMMITTEE" ||
    resolution.status === "APPROVED_WITH_CONDITIONS";

  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden divide-y divide-slate-100">
      {/* Cabecera de Nivel de Atribución */}
      <div className="p-6 bg-slate-50/70">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${levelInfo.badgeClass}`}
              >
                <Award className="w-3.5 h-3.5" />
                {levelInfo.name}
              </span>
              <span className="text-xs text-slate-500 font-medium">
                {resolution.act_number}
              </span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed font-medium">
              {resolution.governance_title || levelInfo.desc}
            </p>
          </div>

          <div className="flex items-center gap-4 bg-white px-4 py-2.5 rounded-xl border border-slate-200 shadow-2xs self-start sm:self-auto">
            <div>
              <span className="text-[10px] uppercase font-bold text-slate-400 block tracking-wider">
                Quórum Estatutario
              </span>
              <span className="text-sm font-extrabold text-slate-800">
                {resolution.votes_cast_count} de {resolution.required_quorum} votos
              </span>
            </div>
            <div
              className={`w-3 h-3 rounded-full ${
                resolution.is_quorum_reached
                  ? "bg-emerald-500 ring-4 ring-emerald-100"
                  : "bg-amber-400 ring-4 ring-amber-100 animate-pulse"
              }`}
            />
          </div>
        </div>

        {/* Roles Requeridos para Sesión */}
        {resolution.required_roles && resolution.required_roles.length > 0 && (
          <div className="mt-4 pt-4 border-t border-slate-200/60 flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-slate-500">
              Miembros estatutarios convocados:
            </span>
            {resolution.required_roles.map((reqRole) => {
              const hasVoted = resolution.votes.some((v) => v.role === reqRole);
              return (
                <span
                  key={reqRole}
                  className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-semibold border ${
                    hasVoted
                      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                      : "bg-slate-100 text-slate-600 border-slate-200"
                  }`}
                >
                  {hasVoted ? (
                    <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                  ) : (
                    <Clock className="w-3 h-3 text-slate-400" />
                  )}
                  {ROLE_LABELS[reqRole] || reqRole}
                </span>
              );
            })}
          </div>
        )}
      </div>

      {/* Historial de Votación Nominal */}
      <div className="p-6 space-y-3">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
          <Users className="w-4 h-4 text-indigo-500" />
          <span>Votación Colegiada y Deliberación Nominal ({resolution.votes.length})</span>
        </h3>

        {resolution.votes.length === 0 ? (
          <p className="text-xs text-slate-500 italic py-2">
            No se han registrado votos aún. La sesión de deliberación está abierta para los miembros convocados.
          </p>
        ) : (
          <div className="space-y-3">
            {resolution.votes.map((v, idx) => {
              const isApp = v.vote === "APPROVE";
              const isCond = v.vote === "CONDITION";
              const badgeStyle = isApp
                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                : isCond
                ? "bg-amber-50 text-amber-700 border-amber-200"
                : "bg-rose-50 text-rose-700 border-rose-200";

              return (
                <div
                  key={idx}
                  className="p-4 rounded-xl border border-slate-100 bg-slate-50/50 space-y-2 text-xs"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-800">
                        {v.voter_name}
                      </span>
                      <span className="text-[11px] text-slate-500 font-medium">
                        ({ROLE_LABELS[v.role] || v.role})
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`px-2.5 py-0.5 rounded-full font-bold border text-[10px] ${badgeStyle}`}
                      >
                        {isApp
                          ? "APROBAR"
                          : isCond
                          ? "CONDICIONAR"
                          : "RECHAZAR"}
                      </span>
                      <span className="text-[10px] text-slate-400">
                        {v.voted_at ? new Date(v.voted_at).toLocaleString() : ""}
                      </span>
                    </div>
                  </div>

                  <p className="text-slate-700 italic leading-relaxed">
                    &ldquo;{v.notes}&rdquo;
                  </p>

                  {v.covenants && v.covenants.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-slate-200/50 space-y-1">
                      <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                        Covenants propuestos por este miembro:
                      </span>
                      {v.covenants.map((c, cIdx) => (
                        <div
                          key={cIdx}
                          className="flex items-center gap-2 text-[11px] text-slate-600 bg-white p-2 rounded-lg border border-slate-200/60"
                        >
                          <span className="font-mono font-bold text-indigo-600">
                            {c.code}
                          </span>
                          <span className="flex-1">{c.description}</span>
                          <span className="text-[10px] text-slate-400 font-medium">
                            Plazo: {c.due_days} días
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Dictamen Resolutivo Final o Formulario de Votación */}
      {isFinal ? (
        <div
          className={`p-6 ${
            isApproved
              ? "bg-emerald-50/50 border-t border-emerald-100"
              : "bg-rose-50/50 border-t border-rose-100"
          }`}
        >
          <div className="flex items-start gap-3">
            <div
              className={`p-2.5 rounded-xl text-white ${
                isApproved ? "bg-emerald-600" : "bg-rose-600"
              }`}
            >
              {isApproved ? (
                <ShieldCheck className="w-6 h-6" />
              ) : (
                <XCircle className="w-6 h-6" />
              )}
            </div>
            <div className="space-y-1 flex-1">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                <h4 className="text-base font-extrabold text-slate-900">
                  {resolution.status === "APPROVED_BY_COMMITTEE"
                    ? "Acta Oficial: Crédito Aprobado por Comité"
                    : resolution.status === "APPROVED_WITH_CONDITIONS"
                    ? "Acta Oficial: Crédito Aprobado con Condiciones"
                    : "Acta Oficial: Crédito Denegado por Comité"}
                </h4>
                <span className="font-mono text-xs font-bold text-slate-700 bg-white px-3 py-1 rounded-lg border border-slate-200">
                  {resolution.act_number}
                </span>
              </div>
              <p className="text-xs text-slate-700 leading-relaxed font-medium">
                {resolution.resolution_notes}
              </p>
            </div>
          </div>

          {/* Covenants Vinculantes Consolidados */}
          {resolution.approved_covenants &&
            resolution.approved_covenants.length > 0 && (
              <div className="mt-4 pt-4 border-t border-slate-200/60 space-y-2">
                <h5 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                  <FileText className="w-4 h-4 text-indigo-600" />
                  <span>Covenants Resolutivos Obligatorios para Desembolso</span>
                </h5>
                <div className="grid grid-cols-1 gap-2">
                  {resolution.approved_covenants.map((cov, idx) => (
                    <div
                      key={idx}
                      className="p-3 bg-white rounded-xl border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs"
                    >
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-indigo-700">
                            {cov.code}
                          </span>
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                            {cov.covenant_type || "CONDICION"}
                          </span>
                        </div>
                        <p className="text-slate-700">{cov.description}</p>
                      </div>
                      <div className="flex items-center gap-1.5 text-slate-500 font-medium whitespace-nowrap">
                        <Clock className="w-3.5 h-3.5 text-slate-400" />
                        <span>Vence en {cov.due_days} días</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

          {resolution.offer_expires_at && (
            <div className="mt-4 p-3 bg-white/80 rounded-xl border border-slate-200 text-xs text-slate-600 flex items-center justify-between">
              <span>Vencimiento de la oferta crediticia aprobada (30 días de vigencia):</span>
              <span className="font-bold text-slate-800">
                {new Date(resolution.offer_expires_at).toLocaleDateString()}
              </span>
            </div>
          )}
        </div>
      ) : (
        /* Formulario de Emisión de Voto */
        <form onSubmit={handleCastVote} className="p-6 bg-slate-50/50 space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-indigo-600" />
              <span>Estación de Votación Nominal Colegiada</span>
            </h4>
            <span className="text-xs text-slate-500">
              Sesión activa conforme a Estatutos
            </span>
          </div>

          {error && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 font-medium flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                Nombre del Miembro Votante
              </label>
              <input
                type="text"
                value={voterName}
                onChange={(e) => setVoterName(e.target.value)}
                placeholder="Ej. Juan Pérez"
                className="w-full text-xs px-3 py-2 bg-white rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                Rol Estatutario en el Comité
              </label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as CommitteeMemberRole)}
                className="w-full text-xs px-3 py-2 bg-white rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="RISK_OFFICER">Oficial de Riesgos</option>
                <option value="CREDIT_MANAGER">Gerente de Crédito</option>
                <option value="OPERATIONS_DIRECTOR">Director de Operaciones</option>
                <option value="BOARD_DIRECTOR">Vocal del Consejo</option>
              </select>
            </div>
          </div>

          {/* Selector de Sentido de Voto */}
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1.5">
              Sentido del Dictamen Nominal
            </label>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => setVote("APPROVE")}
                className={`py-2 px-3 rounded-xl text-xs font-bold border transition flex items-center justify-center gap-1.5 ${
                  vote === "APPROVE"
                    ? "bg-emerald-600 text-white border-emerald-600 shadow-sm"
                    : "bg-white text-slate-700 border-slate-200 hover:bg-slate-100"
                }`}
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Aprobar</span>
              </button>
              <button
                type="button"
                onClick={() => setVote("CONDITION")}
                className={`py-2 px-3 rounded-xl text-xs font-bold border transition flex items-center justify-center gap-1.5 ${
                  vote === "CONDITION"
                    ? "bg-amber-600 text-white border-amber-600 shadow-sm"
                    : "bg-white text-slate-700 border-slate-200 hover:bg-slate-100"
                }`}
              >
                <AlertCircle className="w-3.5 h-3.5" />
                <span>Condicionar</span>
              </button>
              <button
                type="button"
                onClick={() => setVote("REJECT")}
                className={`py-2 px-3 rounded-xl text-xs font-bold border transition flex items-center justify-center gap-1.5 ${
                  vote === "REJECT"
                    ? "bg-rose-600 text-white border-rose-600 shadow-sm"
                    : "bg-white text-slate-700 border-slate-200 hover:bg-slate-100"
                }`}
              >
                <XCircle className="w-3.5 h-3.5" />
                <span>Rechazar</span>
              </button>
            </div>
          </div>

          {/* Constructor de Covenants si se condiciona */}
          {vote === "CONDITION" && (
            <div className="p-4 bg-amber-50/50 rounded-xl border border-amber-200/80 space-y-3">
              <span className="text-xs font-bold text-amber-900 block">
                Covenants o Condiciones Vinculantes Obligatorias
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-2">
                <input
                  type="text"
                  placeholder="Código (Ej. COV-POL-01)"
                  value={newCovCode}
                  onChange={(e) => setNewCovCode(e.target.value)}
                  className="text-xs px-2.5 py-1.5 bg-white rounded-lg border border-amber-300 focus:outline-none"
                />
                <select
                  value={newCovType}
                  onChange={(e) => setNewCovType(e.target.value)}
                  className="text-xs px-2.5 py-1.5 bg-white rounded-lg border border-amber-300 focus:outline-none"
                >
                  <option value="GARANTIA">Garantía / Hipoteca</option>
                  <option value="FINANCIERO">Financiero / Balances</option>
                  <option value="DOCUMENTAL">Documental / Certificados</option>
                </select>
                <input
                  type="number"
                  placeholder="Días plazo (Ej. 30)"
                  value={newCovDays}
                  onChange={(e) => setNewCovDays(Number(e.target.value))}
                  className="text-xs px-2.5 py-1.5 bg-white rounded-lg border border-amber-300 focus:outline-none"
                />
                <button
                  type="button"
                  onClick={handleAddCovenant}
                  className="px-3 py-1.5 rounded-lg text-xs font-bold bg-amber-600 text-white hover:bg-amber-700 flex items-center justify-center gap-1"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Añadir</span>
                </button>
              </div>
              <input
                type="text"
                placeholder="Descripción detallada de la condición estipulada..."
                value={newCovDesc}
                onChange={(e) => setNewCovDesc(e.target.value)}
                className="w-full text-xs px-2.5 py-1.5 bg-white rounded-lg border border-amber-300 focus:outline-none"
              />

              {covenants.length > 0 && (
                <div className="space-y-1 pt-2">
                  {covenants.map((c, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between p-2 bg-white rounded-lg border border-amber-200 text-xs"
                    >
                      <div className="space-x-2">
                        <span className="font-mono font-bold text-amber-800">
                          {c.code}
                        </span>
                        <span className="text-slate-700">{c.description}</span>
                        <span className="text-[10px] text-slate-400">
                          ({c.due_days} días)
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRemoveCovenant(i)}
                        className="text-rose-500 hover:text-rose-700 p-1"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Justificación Técnica */}
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1">
              Justificación Técnica y Fundamentación del Voto
            </label>
            <textarea
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Explique el análisis de riesgo, mitigantes considerados y razones de su voto colegiado..."
              className="w-full text-xs p-3 bg-white rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              required
            />
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={submitting}
              className="px-5 py-2.5 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 transition shadow-sm disabled:opacity-50 flex items-center gap-2"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Registrando Voto...</span>
                </>
              ) : (
                <>
                  <ShieldCheck className="w-4 h-4" />
                  <span>Consignar Voto en Acta</span>
                </>
              )}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
