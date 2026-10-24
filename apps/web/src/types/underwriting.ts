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
  scorecard?: CreditScorecardResult | null;
  historical_precedents?: HistoricalPrecedent[];
  stress_test_results?: StressTestingAnalysis | null;
  collateral_analysis?: UnderwritingCollateralAnalysis | null;
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

export type EventSeverity = "INFO" | "WARNING" | "CRITICAL";

export type CreditEventType =
  | "APPLICATION_SUBMITTED"
  | "METRICS_CALCULATED"
  | "CRITICAL_RISK_DETECTED"
  | "PENDING_HUMAN_REVIEW"
  | "HUMAN_RESOLVED";

export interface CreditUnderwritingEvent {
  event_id: string;
  event_type: CreditEventType;
  severity: EventSeverity;
  application_id: string;
  associated_id: string;
  business_name: string;
  timestamp: string;
  summary: string;
  payload: Record<string, unknown>;
}

export interface FinancialExtractionResult {
  operating_cash_flow: number;
  annual_debt_service: number;
  current_assets: number;
  current_liabilities: number;
  cash_balance: number;
  monthly_burn_rate: number;
  confidence_score: number;
  detected_anomalies: string[];
  extracted_source_name: string;
  summary_notes: string;
}

export type RiskRatingCategory = "A" | "B" | "C" | "D" | "E";

export interface ScorecardBreakdown {
  dscr_score: number;
  liquidity_score: number;
  concentration_score: number;
  ai_alignment_score: number;
}

export interface CreditScorecardResult {
  total_score: number;
  rating_category: RiskRatingCategory;
  category_title: string;
  provision_percentage: number;
  estimated_provision_usd: number;
  breakdown: ScorecardBreakdown;
  regulatory_justification: string;
}

export type StressScenarioType =
  | "BASE"
  | "SALES_SHOCK_MILD"
  | "SALES_SHOCK_MODERATE"
  | "COST_SHOCK"
  | "RATE_SHOCK"
  | "COMBINED_SEVERE"
  | "CUSTOM";

export interface ScenarioStressResult {
  scenario_type: StressScenarioType;
  scenario_name: string;
  description: string;
  stressed_revenue: number;
  stressed_costs: number;
  stressed_ebitda: number;
  stressed_debt_service: number;
  stressed_dscr: number | null;
  stressed_current_ratio: number | null;
  base_rating: RiskRatingCategory;
  stressed_rating: RiskRatingCategory;
  rating_downgraded: boolean;
  base_score: number;
  stressed_score: number;
  base_provision_usd: number;
  stressed_provision_usd: number;
  delta_provision_usd: number;
  is_solvent: boolean;
}

export interface StressTestingAnalysis {
  application_id: string;
  executed_at: string;
  base_scenario: ScenarioStressResult;
  scenarios: ScenarioStressResult[];
  breakeven_sales_drop_pct: number;
  breakeven_tolerable: boolean;
  resilience_summary: string;
}

export type CollateralType =
  | "CDAT_DEPOSIT"
  | "FNG_GUARANTEE"
  | "REAL_ESTATE_URBAN"
  | "REAL_ESTATE_RURAL"
  | "VEHICLE_COMMERCIAL"
  | "INDUSTRIAL_MACHINERY"
  | "PERSONAL_GUARANTEE";

export interface CollateralItemInput {
  collateral_type: CollateralType;
  description: string;
  commercial_appraisal_usd: number;
}

export interface CollateralItem {
  id: string;
  collateral_type: CollateralType;
  description: string;
  commercial_appraisal_usd: number;
  haircut_percentage: number;
  admissible_value_usd: number;
  is_statutory_admissible: boolean;
}

export interface UnderwritingCollateralAnalysis {
  application_id: string;
  evaluated_at: string;
  items: CollateralItem[];
  total_appraisal_usd: number;
  total_admissible_usd: number;
  requested_amount_usd: number;
  ltv_percentage: number | null;
  ltv_status: "HEALTHY" | "WARNING" | "CRITICAL" | "UNSECURED";
  collateral_coverage_ratio: number;
  net_exposure_at_default_usd: number;
  rating_category: string;
  provision_rate_percentage: number;
  gross_provision_usd: number;
  net_provision_usd: number;
  capital_relief_usd: number;
  is_fully_secured: boolean;
  recommendation_notes: string;
}


