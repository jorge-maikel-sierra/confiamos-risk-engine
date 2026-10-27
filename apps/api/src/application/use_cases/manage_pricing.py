"""Casos de Uso: Motor de Pricing Ajustado al Riesgo y Amortizaciones (SPEC-12).

Orquesta la formulación de tasas (COF, OPEX, Riesgo EL, RAROC), control de límites
de usura y generación determinística de tablas de amortización bajo Arquitectura Hexagonal.
"""

from __future__ import annotations

from typing import Any

from src.application.exceptions import ApplicationNotFoundError
from src.domain.pricing import (
    AmortizationSystem,
    PricingProposal,
    RiskBasedPricingEngine,
)
from src.domain.repositories import IUnderwritingRepository


class GeneratePricingUseCase:
    """Caso de uso para calcular y persistir la propuesta de pricing y amortización."""

    def __init__(self, repository: IUnderwritingRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        application_id: str,
        amortization_system: AmortizationSystem = AmortizationSystem.FRENCH,
        term_months_override: int | None = None,
        insurance_rate_monthly: float | None = None,
    ) -> PricingProposal:
        """Calcula el pricing por componentes, valida usura y genera la tabla de cuotas."""
        record = await self.repository.get_by_id(application_id)
        if not record:
            raise ApplicationNotFoundError(application_id)

        requested_amount = float(record.get("requested_amount_usd", 10000.0))
        term_months = term_months_override or int(record.get("term_months", 12))

        # 1. Extraer Rating de SPEC-09
        raw_scorecard: dict[str, Any] = record.get("scorecard") or {}
        rating_category = str(raw_scorecard.get("rating_category", "C"))

        # 2. Extraer LTV y EAD Neta de SPEC-11
        raw_collateral: dict[str, Any] = record.get("collateral_analysis") or {}
        ltv_status = str(raw_collateral.get("ltv_status", "UNSECURED"))
        ead_net = raw_collateral.get("net_exposure_at_default_usd")
        if ead_net is not None:
            ead_net = float(ead_net)
        else:
            ead_net = requested_amount

        # 3. Invocar motor determinístico
        kwargs: dict[str, Any] = {
            "application_id": application_id,
            "requested_amount_usd": requested_amount,
            "term_months": term_months,
            "rating_category": rating_category,
            "ltv_status": ltv_status,
            "net_exposure_at_default_usd": ead_net,
            "amortization_system": amortization_system,
        }
        if insurance_rate_monthly is not None:
            kwargs["insurance_rate_monthly"] = insurance_rate_monthly

        proposal = RiskBasedPricingEngine.calculate_pricing(**kwargs)

        # 4. Persistir en repositorio
        await self.repository.save_pricing_proposal(application_id, proposal.model_dump())
        return proposal


class GetPricingUseCase:
    """Caso de uso para consultar la propuesta de pricing y amortización de un crédito."""

    def __init__(
        self,
        repository: IUnderwritingRepository,
        generate_use_case: GeneratePricingUseCase,
    ) -> None:
        self.repository = repository
        self.generate_use_case = generate_use_case

    async def execute(self, application_id: str) -> PricingProposal:
        """Retorna la propuesta persistida o genera una propuesta base si aún no fue calculada."""
        record = await self.repository.get_by_id(application_id)
        if not record:
            raise ApplicationNotFoundError(application_id)

        saved = record.get("pricing_proposal")
        if saved:
            return PricingProposal(**saved)

        # Si aún no tiene pricing fijado, genera el esquema base por defecto (Francés)
        return await self.generate_use_case.execute(application_id=application_id)
