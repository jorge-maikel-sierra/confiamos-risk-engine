import {
  CreateUnderwritingPayload,
  HumanReviewPayload,
  PaginatedUnderwritingList,
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
