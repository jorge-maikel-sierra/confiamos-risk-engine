"""Casos de Uso: Matriz de Atribuciones y Comité de Crédito Colegiado (SPEC-13).

Orquesta la evaluación de competencia estatutaria, votación multi-rol con quórum
y emisión del Acta Resolutiva Oficial de Comité bajo Arquitectura Hexagonal.
"""

from __future__ import annotations

from typing import Any

from src.application.exceptions import ApplicationNotFoundError
from src.domain.committee import (
    CommitteeMemberRole,
    CommitteeResolution,
    CommitteeVote,
    CommitteeVoteType,
    CreditCovenant,
    GovernanceEngine,
    GovernanceRequirement,
    ResolutionStatus,
)
from src.domain.repositories import IUnderwritingRepository


class EvaluateGovernanceLevelUseCase:
    """Caso de uso para evaluar la instancia decisoria reglamentaria requerida."""

    def __init__(self, repository: IUnderwritingRepository) -> None:
        self.repository = repository

    async def execute(self, application_id: str) -> GovernanceRequirement:
        """Determina el nivel de atribución (1 a 4) según monto, rating, LTV y usura."""
        record = await self.repository.get_by_id(application_id)
        if not record:
            raise ApplicationNotFoundError(application_id)

        requested_amount = float(record.get("requested_amount_usd", 10000.0))

        raw_scorecard: dict[str, Any] = record.get("scorecard") or {}
        rating_category = str(raw_scorecard.get("rating_category", "C"))

        raw_collateral: dict[str, Any] = record.get("collateral_analysis") or {}
        ltv_status = str(raw_collateral.get("ltv_status", "UNSECURED"))

        raw_pricing: dict[str, Any] = record.get("pricing_proposal") or {}
        exceeds_usury = bool(raw_pricing.get("exceeds_usury_cap", False))

        return GovernanceEngine.evaluate_required_level(
            application_id=application_id,
            requested_amount_usd=requested_amount,
            rating_category=rating_category,
            ltv_status=ltv_status,
            exceeds_usury_cap=exceeds_usury,
        )


class CastCommitteeVoteUseCase:
    """Caso de uso para registrar el voto de un miembro y computar la resolución del comité."""

    def __init__(
        self,
        repository: IUnderwritingRepository,
        evaluate_use_case: EvaluateGovernanceLevelUseCase,
    ) -> None:
        self.repository = repository
        self.evaluate_use_case = evaluate_use_case

    async def execute(
        self,
        application_id: str,
        voter_id: str,
        voter_name: str,
        role: CommitteeMemberRole,
        vote: CommitteeVoteType,
        notes: str,
        covenants: list[CreditCovenant] | None = None,
    ) -> CommitteeResolution:
        """Registra el voto del miembro, recalcula el quórum y persiste el acta."""
        record = await self.repository.get_by_id(application_id)
        if not record:
            raise ApplicationNotFoundError(application_id)

        req = await self.evaluate_use_case.execute(application_id)

        saved_resolution = record.get("committee_resolution")
        current_votes: list[CommitteeVote] = []
        act_number: str | None = None

        if saved_resolution:
            existing_res = CommitteeResolution(**saved_resolution)
            if existing_res.is_final:
                raise ValueError("La resolución del comité ya ha sido emitida de forma definitiva.")
            current_votes = existing_res.votes
            act_number = existing_res.act_number

        new_vote = CommitteeVote(
            voter_id=voter_id,
            voter_name=voter_name,
            role=role,
            vote=vote,
            notes=notes,
            covenants=covenants or [],
            voted_at=datetime_now_iso(),
        )

        resolution = GovernanceEngine.tally_resolution(
            requirement=req,
            current_votes=current_votes,
            new_vote=new_vote,
            act_number=act_number,
        )

        is_final = resolution.is_final
        approved: bool | None = None
        if is_final:
            approved = resolution.status in (
                ResolutionStatus.APPROVED_BY_COMMITTEE,
                ResolutionStatus.APPROVED_WITH_CONDITIONS,
            )

        await self.repository.save_committee_resolution(
            application_id=application_id,
            resolution=resolution.model_dump(),
            is_final=is_final,
            approved=approved,
            notes=resolution.resolution_notes,
        )

        return resolution


class GetCommitteeResolutionUseCase:
    """Caso de uso para consultar la resolución de comité o requisitos de deliberación."""

    def __init__(
        self,
        repository: IUnderwritingRepository,
        evaluate_use_case: EvaluateGovernanceLevelUseCase,
    ) -> None:
        self.repository = repository
        self.evaluate_use_case = evaluate_use_case

    async def execute(self, application_id: str) -> CommitteeResolution:
        """Recupera el acta existente o inicializa el estado en deliberación."""
        record = await self.repository.get_by_id(application_id)
        if not record:
            raise ApplicationNotFoundError(application_id)

        saved_resolution = record.get("committee_resolution")
        if saved_resolution:
            return CommitteeResolution(**saved_resolution)

        # Si aún no tiene deliberación iniciada, genera el estado base
        req = await self.evaluate_use_case.execute(application_id)
        return GovernanceEngine.tally_resolution(
            requirement=req,
            current_votes=[],
        )


def datetime_now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
