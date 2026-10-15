"use client";

import { useState } from "react";
import { Check, X, ShieldCheck, Loader2 } from "lucide-react";
import { submitHumanReview } from "@/lib/api";
import { UnderwritingRecord } from "@/types/underwriting";

interface HumanReviewFormProps {
  applicationId: string;
  isCompleted: boolean;
  humanApproved: boolean | null;
  humanNotes: string | null;
  onReviewSubmitted: (record: UnderwritingRecord) => void;
}

export function HumanReviewForm({
  applicationId,
  isCompleted,
  humanApproved,
  humanNotes,
  onReviewSubmitted,
}: HumanReviewFormProps) {
  const [decision, setDecision] = useState<"approve" | "reject" | null>(null);
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (isCompleted) {
    const isApproved = humanApproved === true;
    return (
      <div className={`p-6 rounded-2xl border ${isApproved ? "bg-emerald-50/60 border-emerald-200" : "bg-rose-50/60 border-rose-200"}`}>
        <div className="flex items-center gap-3 mb-3">
          <div className={`p-2 rounded-xl text-white ${isApproved ? "bg-emerald-600" : "bg-rose-600"}`}>
            {isApproved ? <Check className="w-5 h-5" /> : <X className="w-5 h-5" />}
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-900">
              Dictamen Humano Emitido: {isApproved ? "Crédito Aprobado" : "Crédito Rechazado"}
            </h3>
            <span className="text-xs text-slate-500 font-medium">Resolución vinculante registrada en base de datos y Langfuse</span>
          </div>
        </div>
        <div className="mt-3 p-4 bg-white/80 rounded-xl border border-slate-200/60 text-sm text-slate-700">
          <p className="font-semibold text-xs text-slate-500 uppercase tracking-wider mb-1">Notas del Comité de Riesgo:</p>
          <p className="italic">&ldquo;{humanNotes || "Sin observaciones adicionales."}&rdquo;</p>
        </div>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!decision) {
      setError("Por favor seleccione si aprueba o rechaza la solicitud.");
      return;
    }
    if (!notes.trim()) {
      setError("Debe justificar el dictamen del comité con notas de crédito.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const updated = await submitHumanReview(applicationId, {
        approved: decision === "approve",
        notes: notes.trim(),
      });
      onReviewSubmitted(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al registrar dictamen.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="p-6 bg-white rounded-2xl border border-slate-200 shadow-sm">
      <div className="flex items-center gap-2 mb-4">
        <ShieldCheck className="w-5 h-5 text-blue-600" />
        <h3 className="text-base font-bold text-slate-900">
          Resolución del Oficial de Crédito (Human-in-the-loop)
        </h3>
      </div>

      <p className="text-xs text-slate-500 mb-5 font-medium">
        El dictamen final requiere validación humana. Al emitir la resolución, la máquina de estados de LangGraph finalizará la solicitud y registrará el feedback en Langfuse.
      </p>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-700 font-medium">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 mb-4">
        <button
          type="button"
          onClick={() => {
            setDecision("approve");
            setError(null);
          }}
          className={`flex items-center justify-center gap-2 py-3 px-4 rounded-xl border text-sm font-semibold transition ${
            decision === "approve"
              ? "bg-emerald-600 text-white border-emerald-600 shadow-sm"
              : "bg-white text-slate-700 border-slate-200 hover:bg-emerald-50 hover:border-emerald-300"
          }`}
        >
          <Check className="w-4 h-4" />
          Aprobar Solicitud
        </button>

        <button
          type="button"
          onClick={() => {
            setDecision("reject");
            setError(null);
          }}
          className={`flex items-center justify-center gap-2 py-3 px-4 rounded-xl border text-sm font-semibold transition ${
            decision === "reject"
              ? "bg-rose-600 text-white border-rose-600 shadow-sm"
              : "bg-white text-slate-700 border-slate-200 hover:bg-rose-50 hover:border-rose-300"
          }`}
        >
          <X className="w-4 h-4" />
          Rechazar Solicitud
        </button>
      </div>

      <div className="mb-5">
        <label htmlFor="notes" className="block text-xs font-semibold text-slate-700 mb-1">
          Notas de Auditoría y Justificación de Comité *
        </label>
        <textarea
          id="notes"
          rows={3}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Ej: Se aprueba crédito comercial avalado por contratos corporativos verificados y garantías líquidas..."
          className="w-full text-sm rounded-xl border border-slate-200 p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
        />
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 shadow-sm transition"
      >
        {loading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>Emitiendo dictamen en LangGraph...</span>
          </>
        ) : (
          <span>Confirmar y Emitir Dictamen Definitivo</span>
        )}
      </button>
    </form>
  );
}
