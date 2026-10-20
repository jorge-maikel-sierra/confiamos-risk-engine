"""Caso de Uso: Simulación y Consulta de Pruebas de Estrés Financiero (SPEC-10).

Implementa la orquestación bajo Arquitectura Hexagonal para simular escenarios
de sensibilidad determinística sobre el expediente crediticio.
"""

from __future__ import annotations

from typing import Any

from src.application.exceptions import ApplicationNotFoundError
from src.domain.metrics import DSCRResult, FinancialHealthMetrics
from src.domain.repositories import IUnderwritingRepository
from src.domain.scoring import CreditScorecardResult, RegulatoryScorecardEngine
from src.domain.stress_testing import (
    FinancialStressTestingEngine,
    StressParameters,
    StressTestingAnalysis,
)


class StressTestUnderwritingUseCase:
    """Caso de uso para ejecutar la simulación de pruebas de estrés sobre un expediente."""

    def __init__(self, repository: IUnderwritingRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        application_id: str,
        custom_scenario: StressParameters | None = None,
    ) -> StressTestingAnalysis:
        """Calcula el análisis de estrés, persiste los resultados y retorna el agregado."""
        record = await self.repository.get_by_id(application_id)
        if not record:
            raise ApplicationNotFoundError(application_id)

        raw_financials: dict[str, Any] = record.get("raw_financials") or {}
        metrics_dict: dict[str, Any] = record.get("metrics") or {}
        ai_verdict: dict[str, Any] = record.get("ai_verdict") or {}
        raw_scorecard: dict[str, Any] = record.get("scorecard") or {}

        requested_amount_usd = float(record.get("requested_amount_usd", 10000.0))
        operating_cash_flow = float(raw_financials.get("operating_cash_flow", 0.0))
        annual_debt_service = float(raw_financials.get("annual_debt_service", 0.0))
        current_assets = float(raw_financials.get("current_assets", 0.0))
        current_liabilities = float(raw_financials.get("current_liabilities", 0.0))
        cash_balance = float(raw_financials.get("cash_balance", 0.0))
        runway_months = metrics_dict.get("runway_months")
        anomaly_flags = metrics_dict.get("anomaly_flags") or []
        top_client_pct = float(raw_financials.get("top_client_revenue_percentage", 20.0))
        negative_balance_days = int(raw_financials.get("negative_balance_days", 0))
        ai_recommendation = ai_verdict.get("recommendation") if ai_verdict else None

        # Reconstruir o evaluar la scorecard base si no está disponible
        if raw_scorecard:
            base_scorecard = CreditScorecardResult(**raw_scorecard)
        else:
            dscr_val = metrics_dict.get("dscr")
            is_debt_free = annual_debt_service <= 0
            is_solvent = dscr_val >= 1.25 if dscr_val is not None else False
            base_metrics = FinancialHealthMetrics(
                dscr_result=DSCRResult(
                    dscr=dscr_val, is_debt_free=is_debt_free, is_solvent=is_solvent
                ),
                current_ratio=metrics_dict.get("current_ratio"),
                runway_months=runway_months,
                anomaly_flags=anomaly_flags,
            )
            base_scorecard = RegulatoryScorecardEngine.evaluate(
                metrics=base_metrics,
                top_client_percentage=top_client_pct,
                negative_balance_days=negative_balance_days,
                ai_recommendation=ai_recommendation,
                requested_amount_usd=requested_amount_usd,
            )

        analysis = FinancialStressTestingEngine.run_full_analysis(
            application_id=application_id,
            operating_cash_flow=operating_cash_flow,
            annual_debt_service=annual_debt_service,
            current_assets=current_assets,
            current_liabilities=current_liabilities,
            cash_balance=cash_balance,
            runway_months=runway_months,
            anomaly_flags=anomaly_flags,
            top_client_percentage=top_client_pct,
            negative_balance_days=negative_balance_days,
            ai_recommendation=ai_recommendation,
            requested_amount_usd=requested_amount_usd,
            base_scorecard=base_scorecard,
            custom_scenario=custom_scenario,
            annual_revenue=raw_financials.get("annual_revenue"),
            annual_operating_costs=raw_financials.get("annual_operating_costs"),
        )

        await self.repository.save_stress_test_results(application_id, analysis.model_dump())
        return analysis


class GetStressTestAnalysisUseCase:
    """Caso de uso para consultar el análisis de estrés financiero de un expediente."""

    def __init__(
        self,
        repository: IUnderwritingRepository,
        simulator_use_case: StressTestUnderwritingUseCase,
    ) -> None:
        self.repository = repository
        self.simulator_use_case = simulator_use_case

    async def execute(self, application_id: str) -> StressTestingAnalysis:
        """Retorna el análisis persistido o lo simula automáticamente si no existe."""
        record = await self.repository.get_by_id(application_id)
        if not record:
            raise ApplicationNotFoundError(application_id)

        saved = record.get("stress_test_results")
        if saved:
            return StressTestingAnalysis(**saved)

        # Si aún no fue simulado, se computa y persiste on-demand
        return await self.simulator_use_case.execute(application_id)
