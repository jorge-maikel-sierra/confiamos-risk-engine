"""Simulador de Pruebas de Estrés Financiero y Análisis de Sensibilidad (SPEC-10).

Implementa la formulación matemática determinística bajo Arquitectura Hexagonal Pura
para evaluar la resiliencia crediticia de micro y pequeñas empresas asociadas ante choques
adversos de ingresos, inflación de costos operativos e incrementos en tasas de interés.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from src.domain.metrics import DSCRResult, FinancialHealthMetrics
from src.domain.scoring import CreditScorecardResult, RegulatoryScorecardEngine, RiskRatingCategory


class StressScenarioType(StrEnum):
    """Tipos de escenarios de estrés financiero estandarizados."""

    BASE = "BASE"
    SALES_SHOCK_MILD = "SALES_SHOCK_MILD"  # -10% ventas
    SALES_SHOCK_MODERATE = "SALES_SHOCK_MODERATE"  # -20% ventas
    COST_SHOCK = "COST_SHOCK"  # +15% costos operativos
    RATE_SHOCK = "RATE_SHOCK"  # +300 bps en tasa de interés
    COMBINED_SEVERE = "COMBINED_SEVERE"  # -20% ventas, +10% costos, +300 bps
    CUSTOM = "CUSTOM"  # Escenario personalizado


class StressParameters(BaseModel):
    """Parámetros de choque aplicables a un escenario de estrés."""

    sales_shock_pct: float = Field(
        default=0.0,
        ge=0.0,
        le=0.90,
        description="Caída porcentual en ventas/ingresos brutos (0.0 a 0.90)",
    )
    opex_shock_pct: float = Field(
        default=0.0,
        ge=0.0,
        le=2.00,
        description="Incremento porcentual en costos y gastos operativos (0.0 a 2.00)",
    )
    interest_rate_shock_bps: int = Field(
        default=0,
        ge=0,
        le=2000,
        description="Incremento en la tasa de interés en puntos básicos (e.g. 300 = +3.0%)",
    )


class ScenarioStressResult(BaseModel):
    """Resultado del impacto proyectado sobre un escenario de estrés individual."""

    scenario_type: StressScenarioType
    scenario_name: str
    description: str
    stressed_revenue: float
    stressed_costs: float
    stressed_ebitda: float
    stressed_debt_service: float
    stressed_dscr: float | None
    stressed_current_ratio: float | None
    base_rating: RiskRatingCategory
    stressed_rating: RiskRatingCategory
    rating_downgraded: bool
    base_score: float
    stressed_score: float
    base_provision_usd: float
    stressed_provision_usd: float
    delta_provision_usd: float
    is_solvent: bool = Field(description="True si DSCR >= 1.0 y EBITDA > 0")


class StressTestingAnalysis(BaseModel):
    """Análisis consolidado de pruebas de estrés para una solicitud crediticia."""

    application_id: str
    executed_at: str
    base_scenario: ScenarioStressResult
    scenarios: list[ScenarioStressResult]
    breakeven_sales_drop_pct: float = Field(
        description="Porcentaje exacto de caída en ventas soportado antes de que DSCR < 1.0"
    )
    breakeven_tolerable: bool = Field(
        description="True si la PyME tolera al menos 15% de contracción de ingresos sin entrar en insolvencia"
    )
    resilience_summary: str = Field(description="Dictamen cualitativo consolidado de resiliencia")


class FinancialStressTestingEngine:
    """Motor matemático determinístico de simulación y cálculo de estrés."""

    @classmethod
    def calculate_breakeven_sales_drop(
        cls,
        revenue: float,
        costs: float,
        annual_debt_service: float,
    ) -> tuple[float, bool]:
        """Calcula analíticamente la caída de ingresos exacta que sitúa el DSCR en 1.00.

        Fórmula: EBITDA = DebtService => R * (1 - Delta*) - C = DebtService
        => Delta* = 1.0 - (C + DebtService) / R.
        """
        if revenue <= 0:
            return 0.0, False

        required_cash = costs + annual_debt_service
        raw_breakeven = 1.0 - (required_cash / revenue)

        if raw_breakeven <= 0.0:
            return 0.0, False

        clamped = round(min(1.0, raw_breakeven), 4)
        is_tolerable = clamped >= 0.15  # Tolera al menos 15% de caída
        return clamped, is_tolerable

    @classmethod
    def simulate_scenario(
        cls,
        params: StressParameters,
        base_revenue: float,
        base_costs: float,
        base_debt_service: float,
        base_current_assets: float,
        base_current_liabilities: float,
        base_cash_balance: float,
        base_runway: float | None,
        anomaly_flags: list[str],
        top_client_percentage: float,
        negative_balance_days: int,
        ai_recommendation: str | None,
        requested_amount_usd: float,
        base_scorecard: CreditScorecardResult,
        scenario_type: StressScenarioType,
        scenario_name: str,
        description: str,
    ) -> ScenarioStressResult:
        """Simula determinísticamente un escenario de estrés aplicando choques paramétricos."""
        # 1. Aplicación de choques en flujo de resultados
        stressed_revenue = round(base_revenue * (1.0 - params.sales_shock_pct), 2)
        stressed_costs = round(base_costs * (1.0 + params.opex_shock_pct), 2)
        stressed_ebitda = round(stressed_revenue - stressed_costs, 2)

        # 2. Choque de tasa de interés sobre el servicio de la deuda
        rate_shock_decimal = params.interest_rate_shock_bps / 10000.0
        # El shock de tasa impacta el nuevo monto solicitado y el stock de deuda existente
        additional_debt_service = requested_amount_usd * rate_shock_decimal
        stressed_debt_service = round(base_debt_service + additional_debt_service, 2)

        # 3. Recálculo del DSCR
        if stressed_debt_service > 0:
            raw_dscr = stressed_ebitda / stressed_debt_service
            stressed_dscr = round(max(0.0, raw_dscr), 2)
            is_debt_free = False
            is_solvent = stressed_dscr >= 1.0 and stressed_ebitda > 0
        else:
            stressed_dscr = 100.0 if stressed_ebitda > 0 else 0.0
            is_debt_free = True
            is_solvent = stressed_ebitda > 0

        # 4. Impacto en liquidez corriente y runway
        if base_current_liabilities > 0:
            # Una contracción de ingresos reduce cuentas por cobrar / caja inmediata (factor 30 días)
            revenue_impact = (base_revenue - stressed_revenue) * (30.0 / 360.0)
            stressed_assets = max(0.0, base_current_assets - revenue_impact)
            stressed_current_ratio = round(stressed_assets / base_current_liabilities, 2)
        else:
            stressed_current_ratio = None

        if stressed_ebitda < 0:
            monthly_burn = abs(stressed_ebitda) / 12.0
            stressed_runway = (
                round(base_cash_balance / monthly_burn, 1) if monthly_burn > 0 else 0.0
            )
        else:
            stressed_runway = base_runway

        # 5. Re-evaluación oficial con RegulatoryScorecardEngine (SPEC-09)
        stressed_dscr_result = DSCRResult(
            dscr=stressed_dscr if not is_debt_free else None,
            is_debt_free=is_debt_free,
            is_solvent=is_solvent,
        )
        stressed_metrics = FinancialHealthMetrics(
            dscr_result=stressed_dscr_result,
            current_ratio=stressed_current_ratio,
            runway_months=stressed_runway,
            anomaly_flags=anomaly_flags,
        )

        re_scorecard = RegulatoryScorecardEngine.evaluate(
            metrics=stressed_metrics,
            top_client_percentage=top_client_percentage,
            negative_balance_days=negative_balance_days,
            ai_recommendation=ai_recommendation,
            requested_amount_usd=requested_amount_usd,
        )

        delta_provision = round(
            re_scorecard.estimated_provision_usd - base_scorecard.estimated_provision_usd, 2
        )
        downgraded = re_scorecard.total_score < base_scorecard.total_score

        return ScenarioStressResult(
            scenario_type=scenario_type,
            scenario_name=scenario_name,
            description=description,
            stressed_revenue=stressed_revenue,
            stressed_costs=stressed_costs,
            stressed_ebitda=stressed_ebitda,
            stressed_debt_service=stressed_debt_service,
            stressed_dscr=stressed_dscr,
            stressed_current_ratio=stressed_current_ratio,
            base_rating=base_scorecard.rating_category,
            stressed_rating=re_scorecard.rating_category,
            rating_downgraded=downgraded,
            base_score=base_scorecard.total_score,
            stressed_score=re_scorecard.total_score,
            base_provision_usd=base_scorecard.estimated_provision_usd,
            stressed_provision_usd=re_scorecard.estimated_provision_usd,
            delta_provision_usd=delta_provision,
            is_solvent=is_solvent,
        )

    @classmethod
    def run_full_analysis(
        cls,
        application_id: str,
        operating_cash_flow: float,
        annual_debt_service: float,
        current_assets: float,
        current_liabilities: float,
        cash_balance: float,
        runway_months: float | None,
        anomaly_flags: list[str],
        top_client_percentage: float,
        negative_balance_days: int,
        ai_recommendation: str | None,
        requested_amount_usd: float,
        base_scorecard: CreditScorecardResult,
        custom_scenario: StressParameters | None = None,
        annual_revenue: float | None = None,
        annual_operating_costs: float | None = None,
    ) -> StressTestingAnalysis:
        """Ejecuta el catálogo completo de pruebas de estrés normativas y personalizadas."""
        # Resolver ingresos y costos base con benchmark consistente
        if annual_revenue is not None and annual_revenue > 0:
            base_rev = float(annual_revenue)
            base_cost = (
                float(annual_operating_costs)
                if annual_operating_costs is not None
                else max(0.0, base_rev - operating_cash_flow)
            )
        else:
            # Si no se desglosan explícitamente, se asume un margen EBITDA del 20%
            base_rev = max(operating_cash_flow * 5.0, requested_amount_usd * 2.0, 50000.0)
            base_cost = max(0.0, base_rev - operating_cash_flow)

        # 1. Escenario Base (0% de shock)
        base_scenario_res = cls.simulate_scenario(
            params=StressParameters(
                sales_shock_pct=0.0, opex_shock_pct=0.0, interest_rate_shock_bps=0
            ),
            base_revenue=base_rev,
            base_costs=base_cost,
            base_debt_service=annual_debt_service,
            base_current_assets=current_assets,
            base_current_liabilities=current_liabilities,
            base_cash_balance=cash_balance,
            base_runway=runway_months,
            anomaly_flags=anomaly_flags,
            top_client_percentage=top_client_percentage,
            negative_balance_days=negative_balance_days,
            ai_recommendation=ai_recommendation,
            requested_amount_usd=requested_amount_usd,
            base_scorecard=base_scorecard,
            scenario_type=StressScenarioType.BASE,
            scenario_name="Escenario Base",
            description="Condiciones financieras originales del expediente sin choques adicionales.",
        )

        scenarios_to_run = [
            (
                StressScenarioType.SALES_SHOCK_MILD,
                "Shock Leve de Ventas (-10%)",
                "Contracción moderada del 10% en ingresos por caída estacional de demanda.",
                StressParameters(
                    sales_shock_pct=0.10, opex_shock_pct=0.0, interest_rate_shock_bps=0
                ),
            ),
            (
                StressScenarioType.SALES_SHOCK_MODERATE,
                "Shock Moderado de Ventas (-20%)",
                "Caída del 20% en ventas por pérdida de clientes relevantes o recesión en el sector.",
                StressParameters(
                    sales_shock_pct=0.20, opex_shock_pct=0.0, interest_rate_shock_bps=0
                ),
            ),
            (
                StressScenarioType.COST_SHOCK,
                "Shock de Costos (+15%)",
                "Incremento del 15% en costos operativos e insumos por presiones inflacionarias.",
                StressParameters(
                    sales_shock_pct=0.0, opex_shock_pct=0.15, interest_rate_shock_bps=0
                ),
            ),
            (
                StressScenarioType.RATE_SHOCK,
                "Shock de Tasa de Interés (+300 bps)",
                "Subida de 300 puntos básicos (+3.0%) en la tasa activa del crédito otorgado.",
                StressParameters(
                    sales_shock_pct=0.0, opex_shock_pct=0.0, interest_rate_shock_bps=300
                ),
            ),
            (
                StressScenarioType.COMBINED_SEVERE,
                "Adverso Severo Combinado (Estanflación)",
                "Shock múltiple: -20% en ventas, +10% en costos operativos y +300 bps en tasa de interés.",
                StressParameters(
                    sales_shock_pct=0.20, opex_shock_pct=0.10, interest_rate_shock_bps=300
                ),
            ),
        ]

        if custom_scenario:
            scenarios_to_run.append(
                (
                    StressScenarioType.CUSTOM,
                    "Escenario Personalizado de Comité",
                    (
                        f"Simulación a medida: Ventas -{custom_scenario.sales_shock_pct * 100:.1f}%, "
                        f"Costos +{custom_scenario.opex_shock_pct * 100:.1f}%, "
                        f"Tasa +{custom_scenario.interest_rate_shock_bps} bps."
                    ),
                    custom_scenario,
                )
            )

        scenario_results: list[ScenarioStressResult] = []
        for s_type, s_name, s_desc, s_params in scenarios_to_run:
            res = cls.simulate_scenario(
                params=s_params,
                base_revenue=base_rev,
                base_costs=base_cost,
                base_debt_service=annual_debt_service,
                base_current_assets=current_assets,
                base_current_liabilities=current_liabilities,
                base_cash_balance=cash_balance,
                base_runway=runway_months,
                anomaly_flags=anomaly_flags,
                top_client_percentage=top_client_percentage,
                negative_balance_days=negative_balance_days,
                ai_recommendation=ai_recommendation,
                requested_amount_usd=requested_amount_usd,
                base_scorecard=base_scorecard,
                scenario_type=s_type,
                scenario_name=s_name,
                description=s_desc,
            )
            scenario_results.append(res)

        breakeven_drop, is_tolerable = cls.calculate_breakeven_sales_drop(
            revenue=base_rev,
            costs=base_cost,
            annual_debt_service=annual_debt_service,
        )

        severe_res = next(
            (r for r in scenario_results if r.scenario_type == StressScenarioType.COMBINED_SEVERE),
            None,
        )

        if not is_tolerable or (severe_res and not severe_res.is_solvent):
            summary = (
                f"Vulnerabilidad Financiera Detectada: El solicitante soporta un margen de quiebre de "
                f"ingresos de solo {breakeven_drop * 100:.1f}%. Bajo el escenario adverso severo, "
                f"la calificación migra a Categoría {severe_res.stressed_rating.value if severe_res else 'D'} "
                f"con una provisión incremental de ${severe_res.delta_provision_usd:,.2f} USD."
            )
        else:
            summary = (
                f"Resiliencia Financiera Adecuada: La PyME soporta una contracción de ventas de hasta el "
                f"{breakeven_drop * 100:.1f}% antes de comprometer la cobertura de deuda (DSCR < 1.0). "
                f"Bajo estrés severo, mantiene solvencia operativa."
            )

        return StressTestingAnalysis(
            application_id=application_id,
            executed_at=datetime.now(UTC).isoformat(),
            base_scenario=base_scenario_res,
            scenarios=scenario_results,
            breakeven_sales_drop_pct=breakeven_drop,
            breakeven_tolerable=is_tolerable,
            resilience_summary=summary,
        )
