"""Esquemas Pydantic para los endpoints REST de evaluación crediticia (SPEC-01 y SPEC-05)."""

from pydantic import BaseModel, Field

from src.domain.collaterals import CollateralItemInput, UnderwritingCollateralAnalysis
from src.domain.pricing import AmortizationSystem, PricingProposal
from src.domain.scoring import CreditScorecardResult
from src.domain.state import UnderwritingVerdict
from src.domain.stress_testing import StressParameters, StressTestingAnalysis


class RawFinancialsSchema(BaseModel):
    """Datos contables y financieros crudos enviados por el cliente."""

    operating_cash_flow: float = Field(description="Flujo de caja operativo anual")
    annual_debt_service: float = Field(ge=0.0, description="Servicio anual de deuda")
    current_assets: float = Field(ge=0.0, description="Activo corriente total")
    current_liabilities: float = Field(ge=0.0, description="Pasivo corriente total")
    cash_balance: float = Field(ge=0.0, description="Saldo disponible en caja y bancos")
    monthly_burn_rate: float = Field(default=0.0, ge=0.0, description="Gasto neto mensual")
    negative_balance_days: int = Field(default=0, ge=0, description="Días con saldo negativo")
    top_client_revenue_percentage: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Porcentaje de concentración del cliente top"
    )


class UnderwriteRequestSchema(BaseModel):
    """Payload de entrada para iniciar la evaluación crediticia."""

    associated_id: str = Field(description="Identificador del asociado de Cooperativa Confiamos")
    business_name: str = Field(description="Razón social de la empresa o PyME solicitante")
    sector: str = Field(
        default="Comercio y Servicios", description="Sector económico de la empresa solicitante"
    )
    requested_amount_usd: float = Field(gt=0.0, description="Monto solicitado en dólares")
    term_months: int = Field(gt=0, le=120, description="Plazo solicitado en meses")
    financial_data: RawFinancialsSchema = Field(description="Balances y datos contables")


class MetricsSummarySchema(BaseModel):
    """Resumen de indicadores determinísticos calculados por el motor matemático."""

    dscr: float | None = None
    current_ratio: float | None = None
    runway_months: float | None = None
    is_solvent: bool
    is_debt_free: bool
    anomaly_flags: list[str] = Field(default_factory=list)


class HistoricalPrecedentSchema(BaseModel):
    """Precedente histórico de crédito recuperado por similitud semántica (SPEC-05)."""

    loan_id: str
    business_name: str
    sector: str
    requested_amount_usd: float
    dscr: float
    current_ratio: float
    anomaly_flags: list[str] = Field(default_factory=list)
    outcome: str
    outcome_summary: str
    similarity_score: float


class UnderwriteResponseSchema(BaseModel):
    """Respuesta consolidada del estado de la solicitud crediticia."""

    application_id: str
    associated_id: str
    business_name: str
    sector: str = "Comercio y Servicios"
    current_step: str
    is_completed: bool
    metrics: MetricsSummarySchema | None = None
    ai_verdict: UnderwritingVerdict | None = None
    scorecard: CreditScorecardResult | None = None
    historical_precedents: list[HistoricalPrecedentSchema] = Field(default_factory=list)
    stress_test_results: StressTestingAnalysis | None = None
    collateral_analysis: UnderwritingCollateralAnalysis | None = None
    pricing_proposal: PricingProposal | None = None
    human_approved: bool | None = None
    human_notes: str | None = None
    errors: list[str] = Field(default_factory=list)


class HumanReviewRequestSchema(BaseModel):
    """Payload enviado por el oficial de crédito para aprobar o rechazar la solicitud."""

    approved: bool = Field(
        description="Resolución del oficial de crédito (True: Aprueba, False: Rechaza)"
    )
    notes: str = Field(
        min_length=3, description="Justificación o condiciones impuestas por el comité"
    )


class PaginatedUnderwritingListSchema(BaseModel):
    """Respuesta paginada para la bandeja de solicitudes de crédito de oficiales."""

    items: list[UnderwriteResponseSchema]
    total: int
    limit: int
    offset: int


class StressTestRequestSchema(BaseModel):
    """Payload opcional para simular un escenario de estrés personalizado (SPEC-10)."""

    custom_scenario: StressParameters | None = Field(
        default=None, description="Parámetros de choque personalizados definidos por el oficial"
    )


class RegisterCollateralsRequestSchema(BaseModel):
    """Payload para registrar y valuar colaterales de una solicitud (SPEC-11)."""

    collaterals: list[CollateralItemInput] = Field(
        default_factory=list, description="Lista de bienes o títulos aportados en garantía"
    )


class GeneratePricingRequestSchema(BaseModel):
    """Payload opcional para simular o fijar propuesta de pricing y amortización (SPEC-12)."""

    amortization_system: AmortizationSystem = Field(
        default=AmortizationSystem.FRENCH,
        description="Sistema de amortización: FRENCH (Cuota Fija) o GERMAN (Amortización Constante)",
    )
    term_months_override: int | None = Field(
        default=None,
        gt=0,
        le=120,
        description="Plazo en meses opcional para simular diferentes escenarios de amortización",
    )
    insurance_rate_monthly: float | None = Field(
        default=None,
        ge=0.0,
        le=0.05,
        description="Tasa mensual de seguro de cartera (por defecto 0.0012 = 0.12%)",
    )



