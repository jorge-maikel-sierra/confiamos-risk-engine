export type CreditRecommendation =
  | "APROBADO"
  | "APROBADO_CONDICIONADO"
  | "RECHAZADO";

export interface MetricsSummary {
  dscr: number | null;
  current_ratio: number | null;
  runway_months: number | null;
  is_solvent: boolean;
  is_debt_free: boolean;
  anomaly_flags: string[];
}

export interface UnderwritingVerdict {
  recommendation: CreditRecommendation;
  confidence_score: number;
  executive_summary: string;
  key_strengths: string[];
  identified_risks: string[];
  due_diligence_questions: string[];
}

export interface HistoricalPrecedent {
  loan_id: string;
  business_name: string;
  sector: string;
  requested_amount_usd: number;
  dscr: number;
  current_ratio: number;
  anomaly_flags: string[];
  outcome: "CARTERA_SANA" | "DEFAULT_MORA" | "REESTRUCTURADO";
  outcome_summary: string;
  similarity_score: number;
}

export interface UnderwritingRecord {
  application_id: string;
  associated_id: string;
  business_name: string;
  sector?: string;
  current_step: string;
  is_completed: boolean;
  metrics: MetricsSummary | null;
  ai_verdict: UnderwritingVerdict | null;
  historical_precedents?: HistoricalPrecedent[];
  human_approved: boolean | null;
  human_notes: string | null;
  errors: string[];
  created_at?: string;
  updated_at?: string;
}

export interface PaginatedUnderwritingList {
  total: number;
  limit: number;
  offset: number;
  items: UnderwritingRecord[];
}

export interface CreateUnderwritingPayload {
  associated_id: string;
  business_name: string;
  sector?: string;
  requested_amount_usd: number;
  term_months: number;
  financial_data: {
    operating_cash_flow: number;
    annual_debt_service: number;
    current_assets: number;
    current_liabilities: number;
    cash_balance: number;
    monthly_burn_rate: number;
    negative_balance_days: number;
    top_client_revenue_percentage: number;
  };
}

export interface HumanReviewPayload {
  approved: boolean;
  notes: string;
}
