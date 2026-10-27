import {
  AmortizationSystem,
  CollateralItemInput,
  CreateUnderwritingPayload,
  FinancialExtractionResult,
  HumanReviewPayload,
  PaginatedUnderwritingList,
  PricingProposal,
  StressTestingAnalysis,
  UnderwritingCollateralAnalysis,
  UnderwritingRecord,
} from "@/types/underwriting";

export const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export function getUnderwritingEventsUrl(): string {
  return `${BASE_URL}/underwritings/events`;
}

export async function fetchUnderwritings(
  status?: string,
  limit = 20,
  offset = 0
): Promise<PaginatedUnderwritingList> {
  const params = new URLSearchParams({
    limit: limit.toString(),
    offset: offset.toString(),
  });
  if (status) {
    params.append("status", status);
  }

  const res = await fetch(`${BASE_URL}/underwritings?${params.toString()}`, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`Error al listar solicitudes: ${res.statusText}`);
  }

  return res.json();
}

export async function fetchUnderwritingById(
  id: string
): Promise<UnderwritingRecord> {
  const res = await fetch(`${BASE_URL}/underwritings/${encodeURIComponent(id)}`, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`Error al obtener solicitud ${id}: ${res.statusText}`);
  }

  return res.json();
}

export async function createUnderwriting(
  payload: CreateUnderwritingPayload
): Promise<UnderwritingRecord> {
  const res = await fetch(`${BASE_URL}/underwritings`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Error al radicar solicitud");
  }

  return res.json();
}

export async function submitHumanReview(
  id: string,
  payload: HumanReviewPayload
): Promise<UnderwritingRecord> {
  const res = await fetch(
    `${BASE_URL}/underwritings/${encodeURIComponent(id)}/reviews`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    }
  );

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Error al emitir dictamen");
  }

  return res.json();
}

export function getPdfExportUrl(id: string): string {
  return `${BASE_URL}/underwritings/${encodeURIComponent(id)}/export/pdf`;
}

export function getExcelExportUrl(id: string): string {
  return `${BASE_URL}/underwritings/${encodeURIComponent(id)}/export/excel`;
}

export interface SealVerificationResult {
  application_id: string;
  expected_hash: string;
  provided_hash: string | null;
  is_authentic: boolean;
  verified_at: string;
}

export async function verifyIntegritySeal(
  id: string,
  hash?: string
): Promise<SealVerificationResult> {
  const url = new URL(
    `${BASE_URL}/underwritings/${encodeURIComponent(id)}/verify-seal`
  );
  if (hash) {
    url.searchParams.set("hash", hash);
  }
  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Error al verificar sello: ${res.statusText}`);
  }
  return res.json();
}

export async function uploadFinancialDocument(
  file: File
): Promise<FinancialExtractionResult> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${BASE_URL}/underwritings/upload-financials`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Error al procesar el archivo (${res.statusText})`);
  }

  return res.json();
}

export async function fetchStressTestAnalysis(
  id: string
): Promise<StressTestingAnalysis> {
  const res = await fetch(
    `${BASE_URL}/underwritings/${encodeURIComponent(id)}/stress-test`,
    { cache: "no-store" }
  );
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Error al obtener análisis de estrés");
  }
  return res.json();
}

export async function runStressTestSimulation(
  id: string,
  customScenario?: {
    sales_shock_pct?: number;
    opex_shock_pct?: number;
    interest_rate_shock_bps?: number;
  }
): Promise<StressTestingAnalysis> {
  const res = await fetch(
    `${BASE_URL}/underwritings/${encodeURIComponent(id)}/stress-test`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(
        customScenario ? { custom_scenario: customScenario } : {}
      ),
    }
  );

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Error al simular prueba de estrés");
  }

  return res.json();
}

export async function fetchCollateralAnalysis(
  id: string
): Promise<UnderwritingCollateralAnalysis> {
  const res = await fetch(
    `${BASE_URL}/underwritings/${encodeURIComponent(id)}/collaterals`,
    { cache: "no-store" }
  );
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Error al obtener análisis de garantías");
  }
  return res.json();
}

export async function registerCollaterals(
  id: string,
  collaterals: CollateralItemInput[]
): Promise<UnderwritingCollateralAnalysis> {
  const res = await fetch(
    `${BASE_URL}/underwritings/${encodeURIComponent(id)}/collaterals`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ collaterals }),
    }
  );

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Error al registrar garantías");
  }

  return res.json();
}

export async function fetchPricingProposal(id: string): Promise<PricingProposal> {
  const res = await fetch(
    `${BASE_URL}/underwritings/${encodeURIComponent(id)}/pricing`,
    { cache: "no-store" }
  );
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Error al obtener propuesta de pricing");
  }
  return res.json();
}

export async function generatePricingProposal(
  id: string,
  options?: {
    amortization_system?: AmortizationSystem;
    term_months_override?: number;
    insurance_rate_monthly?: number;
  }
): Promise<PricingProposal> {
  const res = await fetch(
    `${BASE_URL}/underwritings/${encodeURIComponent(id)}/pricing`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(options || {}),
    }
  );

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Error al calcular propuesta de pricing");
  }

  return res.json();
}


