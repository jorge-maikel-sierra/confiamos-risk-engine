"""Contratos de puertos del Patrón Repositorio (Dominio Puro - Arquitectura Hexagonal)."""

from abc import ABC, abstractmethod
from typing import Any


class IUnderwritingRepository(ABC):
    """Contrato abstracto (Puerto) para la persistencia y consulta de evaluaciones crediticias."""

    @abstractmethod
    async def create_application(
        self,
        application_id: str,
        associated_id: str,
        business_name: str,
        requested_amount_usd: float,
        term_months: int,
        raw_financials: dict[str, Any],
    ) -> dict[str, Any]:
        """Crea el registro inicial de una solicitud crediticia."""
        ...

    @abstractmethod
    async def get_by_id(self, application_id: str) -> dict[str, Any] | None:
        """Recupera la solicitud por su ID único."""
        ...

    @abstractmethod
    async def list_applications(
        self,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retorna una lista paginada de solicitudes con filtro de estado opcional."""
        ...

    @abstractmethod
    async def update_snapshot(
        self,
        application_id: str,
        current_step: str,
        metrics: dict[str, Any] | None = None,
        ai_verdict: dict[str, Any] | None = None,
        historical_precedents: list[dict[str, Any]] | None = None,
        scorecard: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Actualiza el estado intermedio y resultados de cómputo del StateGraph."""
        ...

    @abstractmethod
    async def submit_human_review(
        self,
        application_id: str,
        approved: bool,
        notes: str,
        current_step: str = "COMPLETED",
    ) -> dict[str, Any]:
        """Registra la intervención humana y marca la solicitud como completada."""
        ...
