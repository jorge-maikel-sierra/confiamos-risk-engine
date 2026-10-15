"use client";

import React, { useState, useRef } from "react";
import {
  UploadCloud,
  FileText,
  FileSpreadsheet,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Sparkles,
  X,
} from "lucide-react";
import { uploadFinancialDocument } from "@/lib/api";
import { FinancialExtractionResult } from "@/types/underwriting";

interface DocumentDropzoneProps {
  onExtracted: (result: FinancialExtractionResult) => void;
}

export function DocumentDropzone({ onExtracted }: DocumentDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [extractionResult, setExtractionResult] =
    useState<FinancialExtractionResult | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      await processFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      await processFile(e.target.files[0]);
    }
  };

  const processFile = async (file: File) => {
    setError(null);

    // Validación preliminar en navegador (10 MB)
    if (file.size > 10 * 1024 * 1024) {
      setError("El archivo excede el tamaño máximo permitido de 10 MB.");
      return;
    }

    const ext = file.name.split(".").pop()?.toLowerCase();
    if (!ext || !["pdf", "xlsx", "xls"].includes(ext)) {
      setError(
        "Formato no admitido. Por favor cargue un archivo PDF o planilla Excel (.xlsx, .xls)."
      );
      return;
    }

    setUploading(true);

    try {
      const result = await uploadFinancialDocument(file);
      setExtractionResult(result);
      onExtracted(result);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Error durante la extracción documental en el backend."
      );
    } finally {
      setUploading(false);
    }
  };

  const handleClear = () => {
    setExtractionResult(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <div className="space-y-3">
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileSelect}
        accept=".pdf,.xlsx,.xls"
        className="hidden"
      />

      {!extractionResult ? (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !uploading && fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-2xl p-6 text-center cursor-pointer transition flex flex-col items-center justify-center gap-3 ${
            isDragging
              ? "border-blue-500 bg-blue-50/60"
              : "border-slate-200 hover:border-blue-400 hover:bg-slate-50/50 bg-white"
          } ${uploading ? "opacity-75 cursor-wait" : ""}`}
        >
          {uploading ? (
            <div className="flex flex-col items-center gap-2 py-4">
              <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
              <p className="text-sm font-bold text-slate-800">
                Procesando Documento Financiero...
              </p>
              <p className="text-xs text-slate-500">
                Extrayendo flujos, balances y activos con IA y openpyxl
              </p>
            </div>
          ) : (
            <>
              <div className="w-12 h-12 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center shadow-inner">
                <UploadCloud className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm font-bold text-slate-800">
                  Arrastre aquí el Balance General o Extracto Bancario
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  Formatos admitidos: <span className="font-semibold text-slate-700">PDF, Excel (.xlsx, .xls)</span> hasta 10 MB
                </p>
              </div>
              <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 text-[11px] font-semibold text-slate-600">
                <Sparkles className="w-3.5 h-3.5 text-blue-600" />
                <span>Extracción Inteligente y Autocompletado del Formulario</span>
              </div>
            </>
          )}
        </div>
      ) : (
        <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-950 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center flex-shrink-0 mt-0.5">
              {extractionResult.extracted_source_name.endsWith(".pdf") ? (
                <FileText className="w-5 h-5" />
              ) : (
                <FileSpreadsheet className="w-5 h-5" />
              )}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h4 className="text-sm font-bold text-slate-900">
                  {extractionResult.extracted_source_name}
                </h4>
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-200/60 text-emerald-800">
                  <CheckCircle2 className="w-3 h-3" />
                  {Math.round(extractionResult.confidence_score * 100)}% Confianza
                </span>
              </div>
              <p className="text-xs text-slate-600 mt-0.5">
                {extractionResult.summary_notes}
              </p>
              {extractionResult.detected_anomalies.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {extractionResult.detected_anomalies.map((anom, i) => (
                    <span
                      key={i}
                      className="px-2 py-0.5 rounded bg-amber-100 text-amber-800 text-[10px] font-medium"
                    >
                      ⚠️ {anom}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 self-end md:self-center">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 transition shadow-sm"
            >
              Cambiar Archivo
            </button>
            <button
              type="button"
              onClick={handleClear}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
              title="Quitar archivo"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 flex items-center gap-2 text-xs">
          <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
