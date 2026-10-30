"""Implementaciones concretas del Patrón Repositorio (Adaptadores de Infraestructura).

Cumple con el puerto IUnderwritingRepository definido en src.domain.repositories.
"""

from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.repositories import IUnderwritingRepository
from src.infrastructure.models import CreditApplicationModel


class InMemoryUnderwritingRepository(IUnderwritingRepository):
    """Implementación en memoria volátil para tests unitarios rápidos y CI."""

    def __init__(self) -> None:
        self._storage: dict[str, dict[str, Any]] = {}

    async def create_application(
        self,
        application_id: str,
        associated_id: str,
        business_name: str,
        requested_amount_usd: float,
        term_months: int,
        raw_financials: dict[str, Any],
    ) -> dict[str, Any]:
        record: dict[str, Any] = {
            "application_id": application_id,
            "associated_id": associated_id,
            "business_name": business_name,
            "requested_amount_usd": requested_amount_usd,
            "term_months": term_months,
            "current_step": "INITIALIZED",
            "is_completed": False,
            "raw_financials": raw_financials,
            "metrics": None,
            "ai_verdict": None,
            "scorecard": None,
            "historical_precedents": [],
            "stress_test_results": None,
            "collateral_analysis": None,
            "human_approved": None,
            "human_notes": None,
        }
        self._storage[application_id] = record
        return record

    async def get_by_id(self, application_id: str) -> dict[str, Any] | None:
        return self._storage.get(application_id)

    async def list_applications(
        self,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        records = list(self._storage.values())
        if status:
            records = [r for r in records if r.get("current_step") == status]
        return records[offset : offset + limit]

    async def update_snapshot(
        self,
        application_id: str,
        current_step: str,
        metrics: dict[str, Any] | None = None,
        ai_verdict: dict[str, Any] | None = None,
        historical_precedents: list[dict[str, Any]] | None = None,
        scorecard: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record = self._storage.get(application_id)
        if not record:
            raise KeyError(f"Solicitud {application_id} no encontrada en repositorio en memoria.")
        record["current_step"] = current_step
        if metrics is not None:
            record["metrics"] = metrics
        if ai_verdict is not None:
            record["ai_verdict"] = ai_verdict
        if historical_precedents is not None:
            record["historical_precedents"] = historical_precedents
        if scorecard is not None:
            record["scorecard"] = scorecard
        return record

    async def submit_human_review(
        self,
        application_id: str,
        approved: bool,
        notes: str,
        current_step: str = "COMPLETED",
    ) -> dict[str, Any]:
        record = self._storage.get(application_id)
        if not record:
            raise KeyError(f"Solicitud {application_id} no encontrada en repositorio en memoria.")
        record["human_approved"] = approved
        record["human_notes"] = notes
        record["current_step"] = current_step
        record["is_completed"] = True
        return record

    async def save_stress_test_results(
        self,
        application_id: str,
        results: dict[str, Any],
    ) -> dict[str, Any]:
        record = self._storage.get(application_id)
        if not record:
            raise KeyError(f"Solicitud {application_id} no encontrada en repositorio en memoria.")
        record["stress_test_results"] = results
        return record

    async def save_collateral_analysis(
        self,
        application_id: str,
        analysis: dict[str, Any],
    ) -> dict[str, Any]:
        record = self._storage.get(application_id)
        if not record:
            raise KeyError(f"Solicitud {application_id} no encontrada en repositorio en memoria.")
        record["collateral_analysis"] = analysis
        return record

    async def save_pricing_proposal(
        self,
        application_id: str,
        pricing: dict[str, Any],
    ) -> dict[str, Any]:
        record = self._storage.get(application_id)
        if not record:
            raise KeyError(f"Solicitud {application_id} no encontrada en repositorio en memoria.")
        record["pricing_proposal"] = pricing
        return record

    async def save_committee_resolution(
        self,
        application_id: str,
        resolution: dict[str, Any],
        is_final: bool = False,
        approved: bool | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        record = self._storage.get(application_id)
        if not record:
            raise KeyError(f"Solicitud {application_id} no encontrada en repositorio en memoria.")
        record["committee_resolution"] = resolution
        if is_final:
            record["is_completed"] = True
            record["current_step"] = "COMPLETED"
            if approved is not None:
                record["human_approved"] = approved
            if notes is not None:
                record["human_notes"] = notes
        return record




class PostgresUnderwritingRepository(IUnderwritingRepository):
    """Implementación relacional asíncrona respaldada por PostgreSQL / SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_application(
        self,
        application_id: str,
        associated_id: str,
        business_name: str,
        requested_amount_usd: float,
        term_months: int,
        raw_financials: dict[str, Any],
    ) -> dict[str, Any]:
        model = CreditApplicationModel(
            id=application_id,
            associated_id=associated_id,
            business_name=business_name,
            requested_amount_usd=requested_amount_usd,
            term_months=term_months,
            current_step="INITIALIZED",
            is_completed=False,
            raw_financials=raw_financials,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return model.to_dict()

    async def get_by_id(self, application_id: str) -> dict[str, Any] | None:
        stmt = select(CreditApplicationModel).where(CreditApplicationModel.id == application_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_dict() if model else None

    async def list_applications(
        self,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        stmt = select(CreditApplicationModel).order_by(desc(CreditApplicationModel.created_at))
        if status:
            stmt = stmt.where(CreditApplicationModel.current_step == status)
        stmt = stmt.offset(offset).limit(limit)

        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [m.to_dict() for m in models]

    async def update_snapshot(
        self,
        application_id: str,
        current_step: str,
        metrics: dict[str, Any] | None = None,
        ai_verdict: dict[str, Any] | None = None,
        historical_precedents: list[dict[str, Any]] | None = None,
        scorecard: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        stmt = select(CreditApplicationModel).where(CreditApplicationModel.id == application_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise KeyError(f"Solicitud {application_id} no encontrada en base de datos.")

        model.current_step = current_step
        if metrics is not None:
            model.metrics = metrics
        if ai_verdict is not None:
            model.ai_verdict = ai_verdict
        if historical_precedents is not None:
            model.historical_precedents = historical_precedents
        if scorecard is not None:
            model.scorecard = scorecard

        await self.session.flush()
        await self.session.refresh(model)
        return model.to_dict()

    async def submit_human_review(
        self,
        application_id: str,
        approved: bool,
        notes: str,
        current_step: str = "COMPLETED",
    ) -> dict[str, Any]:
        stmt = select(CreditApplicationModel).where(CreditApplicationModel.id == application_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise KeyError(f"Solicitud {application_id} no encontrada en base de datos.")

        model.human_approved = approved
        model.human_notes = notes
        model.current_step = current_step
        model.is_completed = True

        await self.session.flush()
        await self.session.refresh(model)
        return model.to_dict()

    async def save_stress_test_results(
        self,
        application_id: str,
        results: dict[str, Any],
    ) -> dict[str, Any]:
        stmt = select(CreditApplicationModel).where(CreditApplicationModel.id == application_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise KeyError(f"Solicitud {application_id} no encontrada en base de datos.")

        model.stress_test_results = results
        await self.session.flush()
        await self.session.refresh(model)
        return model.to_dict()

    async def save_collateral_analysis(
        self,
        application_id: str,
        analysis: dict[str, Any],
    ) -> dict[str, Any]:
        stmt = select(CreditApplicationModel).where(CreditApplicationModel.id == application_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise KeyError(f"Solicitud {application_id} no encontrada en base de datos.")

        model.collateral_analysis = analysis
        await self.session.flush()
        await self.session.refresh(model)
        return model.to_dict()

    async def save_pricing_proposal(
        self,
        application_id: str,
        pricing: dict[str, Any],
    ) -> dict[str, Any]:
        stmt = select(CreditApplicationModel).where(CreditApplicationModel.id == application_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise KeyError(f"Solicitud {application_id} no encontrada en base de datos.")

        model.pricing_proposal = pricing
        await self.session.flush()
        await self.session.refresh(model)
        return model.to_dict()

    async def save_committee_resolution(
        self,
        application_id: str,
        resolution: dict[str, Any],
        is_final: bool = False,
        approved: bool | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        stmt = select(CreditApplicationModel).where(CreditApplicationModel.id == application_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise KeyError(f"Solicitud {application_id} no encontrada en base de datos.")

        model.committee_resolution = resolution
        if is_final:
            model.is_completed = True
            model.current_step = "COMPLETED"
            if approved is not None:
                model.human_approved = approved
            if notes is not None:
                model.human_notes = notes

        await self.session.flush()
        await self.session.refresh(model)
        return model.to_dict()


