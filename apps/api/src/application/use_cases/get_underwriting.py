"""Casos de Uso de Consulta: Obtener y Listar Expedientes Crediticios.

Implementa los casos de uso de solo lectura (Driving Ports de consulta).
"""

from dataclasses import dataclass
from typing import Any

from src.application.exceptions import ApplicationNotFoundError
from src.domain.repositories import IUnderwritingRepository


@dataclass(frozen=True)
class ListUnderwritingsQuery:
    """Parámetros de consulta para listado paginado."""

    limit: int = 20
    offset: int = 0
    status_filter: str | None = None


class GetUnderwritingByIdUseCase:
    """Caso de uso: Consultar expediente crediticio por ID."""

    def __init__(self, repository: IUnderwritingRepository) -> None:
        self.repository = repository

    async def execute(self, application_id: str) -> dict[str, Any]:
        """Recupera la solicitud o lanza ApplicationNotFoundError."""
        record = await self.repository.get_by_id(application_id)
        if not record:
            raise ApplicationNotFoundError(application_id)
        return record


class ListUnderwritingsUseCase:
    """Caso de uso: Listar solicitudes de crédito con filtros y paginación."""

    def __init__(self, repository: IUnderwritingRepository) -> None:
        self.repository = repository

    async def execute(self, query: ListUnderwritingsQuery) -> tuple[list[dict[str, Any]], int]:
        """Retorna la tupla (registros, total)."""
        records = await self.repository.list_applications(
            limit=query.limit,
            offset=query.offset,
            status=query.status_filter,
        )
        return records, len(records)
