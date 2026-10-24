"""Casos de Uso: Valuación y Consulta de Garantías y LTV (SPEC-11).

Orquesta el cálculo de LTV, cobertura, EAD neta y provisión neta descontando
colaterales admisibles bajo Arquitectura Hexagonal.
"""

from __future__ import annotations

from typing import Any

from src.application.exceptions import ApplicationNotFoundError
from src.domain.collaterals import (
    CollateralItemInput,
    CollateralValuationEngine,
    UnderwritingCollateralAnalysis,
)
from src.domain.repositories import IUnderwritingRepository


class RegisterCollateralsUseCase:
    """Caso de uso para registrar y valuar colaterales aportados para un crédito."""

    def __init__(self, repository: IUnderwritingRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        application_id: str,
        items: list[CollateralItemInput],
    ) -> UnderwritingCollateralAnalysis:
        """Valúa las garantías, recalcula LTV y provisión neta y persiste el resultado."""
        record = await self.repository.get_by_id(application_id)
        if not record:
            raise ApplicationNotFoundError(application_id)

        requested_amount = float(record.get("requested_amount_usd", 10000.0))
        raw_scorecard: dict[str, Any] = record.get("scorecard") or {}

        # Obtener rating y provisión bruta de la scorecard oficial (SPEC-09)
        rating_category = str(raw_scorecard.get("rating_category", "C"))
        provision_rate = float(raw_scorecard.get("provision_percentage", 10.0))
        gross_provision = float(
            raw_scorecard.get("estimated_provision_usd", requested_amount * (provision_rate / 100.0))
        )

        analysis = CollateralValuationEngine.evaluate(
            application_id=application_id,
            requested_amount_usd=requested_amount,
            rating_category=rating_category,
            provision_rate_percentage=provision_rate,
            gross_provision_usd=gross_provision,
            items_input=items,
        )

        await self.repository.save_collateral_analysis(application_id, analysis.model_dump())
        return analysis


class GetCollateralAnalysisUseCase:
    """Caso de uso para consultar el análisis de garantías de un expediente."""

    def __init__(
        self,
        repository: IUnderwritingRepository,
        register_use_case: RegisterCollateralsUseCase,
    ) -> None:
        self.repository = repository
        self.register_use_case = register_use_case

    async def execute(self, application_id: str) -> UnderwritingCollateralAnalysis:
        """Retorna el análisis persistido o genera el análisis base no garantizado si no existe."""
        record = await self.repository.get_by_id(application_id)
        if not record:
            raise ApplicationNotFoundError(application_id)

        saved = record.get("collateral_analysis")
        if saved:
            return UnderwritingCollateralAnalysis(**saved)

        # Si aún no tiene colaterales radicados, genera el análisis base UNSECURED
        return await self.register_use_case.execute(application_id=application_id, items=[])
