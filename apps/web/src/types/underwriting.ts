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
  pricing_proposal?: PricingProposal | null;
  committee_resolution?: CommitteeResolution | null;
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

export type AmortizationSystem = "FRENCH" | "GERMAN";

export interface PaymentPeriodQuota {
  period: number;
  beginning_balance: number;
  principal_amortization: number;
  interest_payment: number;
  insurance_payment: number;
  total_quota: number;
  ending_balance: number;
}

export interface PricingProposal {
  application_id: string;
  calculated_at: string;
  requested_amount_usd: number;
  term_months: number;
  amortization_system: AmortizationSystem;
  rating_category: string;
  ltv_status: string;
  probability_of_default_pct: number;
  loss_given_default_pct: number;
  net_exposure_at_default_usd: number;
  expected_loss_usd: number;
  expected_loss_rate_ea: number;
  cost_of_funds_ea: number;
  opex_spread_ea: number;
  raroc_target_ea: number;
  uncapped_tea: number;
  applied_tea: number;
  monthly_effective_rate_pct: number;
  usury_cap_tea: number;
  exceeds_usury_cap: boolean;
  usury_adjustment_delta: number;
  first_month_quota_usd: number;
  total_interest_usd: number;
  total_insurance_usd: number;
  total_cost_of_credit_usd: number;
  recommendation_notes: string;
  amortization_schedule: PaymentPeriodQuota[];
}

export type ApprovalAuthorityLevel =
  | "LEVEL_1_OFFICER"
  | "LEVEL_2_MANAGER"
  | "LEVEL_3_COMMITTEE"
  | "LEVEL_4_BOARD";

export type CommitteeVoteType = "APPROVE" | "CONDITION" | "REJECT";

export type CommitteeMemberRole =
  | "RISK_OFFICER"
  | "CREDIT_MANAGER"
  | "OPERATIONS_DIRECTOR"
  | "BOARD_DIRECTOR";

export type ResolutionStatus =
  | "IN_DELIBERATION"
  | "APPROVED_BY_COMMITTEE"
  | "APPROVED_WITH_CONDITIONS"
  | "REJECTED_BY_COMMITTEE";

export interface CreditCovenant {
  code: string;
  description: string;
  covenant_type?: string;
  due_days: number;
}

export interface CommitteeVote {
  voter_id: string;
  voter_name: string;
  role: CommitteeMemberRole;
  vote: CommitteeVoteType;
  notes: string;
  covenants: CreditCovenant[];
  voted_at: string;
}

export interface CommitteeResolution {
  application_id: string;
  act_number: string;
  governance_level: ApprovalAuthorityLevel;
  governance_title: string;
  status: ResolutionStatus;
  required_quorum: number;
  required_roles: CommitteeMemberRole[];
  votes_cast_count: number;
  is_quorum_reached: boolean;
  votes: CommitteeVote[];
  approved_covenants: CreditCovenant[];
  resolution_notes: string;
  resolved_at: string | null;
  offer_expires_at: string | null;
  is_final: boolean;
}



