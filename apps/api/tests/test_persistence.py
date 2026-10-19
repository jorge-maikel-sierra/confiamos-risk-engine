"""Tests unitarios y de persistencia relacional para el Patrón Repositorio.

Issue #11 / SPEC-02.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.infrastructure.database import Base
from src.infrastructure.repositories import (
    InMemoryUnderwritingRepository,
    PostgresUnderwritingRepository,
)


@pytest.fixture
def sample_app_data() -> dict:
    return {
        "application_id": "APP-TEST01",
        "associated_id": "CONF-88123",
        "business_name": "Agroindustrias del Valle",
        "requested_amount_usd": 50000.0,
        "term_months": 36,
        "raw_financials": {
            "operating_cash_flow": 30000.0,
            "annual_debt_service": 12000.0,
        },
    }


@pytest.mark.asyncio
async def test_in_memory_repository_full_lifecycle(sample_app_data: dict) -> None:
    """Verifica el ciclo de vida completo en el repositorio en memoria."""
    repo = InMemoryUnderwritingRepository()

    # 1. Crear
    created = await repo.create_application(**sample_app_data)
    assert created["application_id"] == "APP-TEST01"
    assert created["current_step"] == "INITIALIZED"
    assert created["is_completed"] is False

    # 2. Consultar
    found = await repo.get_by_id("APP-TEST01")
    assert found is not None
    assert found["business_name"] == "Agroindustrias del Valle"

    not_found = await repo.get_by_id("APP-NONEXISTENT")
    assert not_found is None

    # 3. Actualizar snapshot con métricas
    metrics = {"dscr": 2.5, "is_solvent": True}
    ai_verdict = {"recommendation": "APROBADO", "confidence_score": 0.95}
    updated = await repo.update_snapshot(
        application_id="APP-TEST01",
        current_step="PENDING_HUMAN_REVIEW",
        metrics=metrics,
        ai_verdict=ai_verdict,
    )
    assert updated["current_step"] == "PENDING_HUMAN_REVIEW"
    assert updated["metrics"] == metrics
    assert updated["ai_verdict"] == ai_verdict

    # 4. Revisión humana
    reviewed = await repo.submit_human_review(
        application_id="APP-TEST01",
        approved=True,
        notes="Garantía hipotecaria validada.",
    )
    assert reviewed["is_completed"] is True
    assert reviewed["human_approved"] is True
    assert reviewed["current_step"] == "COMPLETED"

    # 5. Listar
    records = await repo.list_applications(limit=10, offset=0, status="COMPLETED")
    assert len(records) == 1
    assert records[0]["application_id"] == "APP-TEST01"


@pytest.mark.asyncio
async def test_postgres_repository_with_async_sqlite(sample_app_data: dict) -> None:
    """Verifica PostgresUnderwritingRepository contra motor asíncrono en memoria."""
    # Motor asíncrono SQLite en memoria para test unitario aislado
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Crear tablas
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        repo = PostgresUnderwritingRepository(session)

        # 1. Crear
        created = await repo.create_application(**sample_app_data)
        assert created["application_id"] == "APP-TEST01"
        assert created["current_step"] == "INITIALIZED"

        # 2. Consultar
        found = await repo.get_by_id("APP-TEST01")
        assert found is not None
        assert found["associated_id"] == "CONF-88123"
        assert found["raw_financials"]["operating_cash_flow"] == 30000.0

        # 3. Actualizar snapshot con métricas
        metrics = {"dscr": 2.5, "is_solvent": True}
        ai_verdict = {"recommendation": "APROBADO", "confidence_score": 0.95}
        updated = await repo.update_snapshot(
            application_id="APP-TEST01",
            current_step="PENDING_HUMAN_REVIEW",
            metrics=metrics,
            ai_verdict=ai_verdict,
        )
        assert updated["current_step"] == "PENDING_HUMAN_REVIEW"
        assert updated["metrics"]["dscr"] == 2.5

        # 4. Revisión humana
        reviewed = await repo.submit_human_review(
            application_id="APP-TEST01",
            approved=False,
            notes="Capacidad de pago insuficiente para el plazo solicitado.",
        )
        assert reviewed["is_completed"] is True
        assert reviewed["human_approved"] is False

        # 5. Listado y paginación
        items = await repo.list_applications(limit=5, offset=0, status="COMPLETED")
        assert len(items) == 1
        assert items[0]["application_id"] == "APP-TEST01"

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_repository_not_found_errors() -> None:
    """Verifica que update y review sobre IDs inexistentes levanten KeyError."""
    mem_repo = InMemoryUnderwritingRepository()
    with pytest.raises(KeyError):
        await mem_repo.update_snapshot("APP-FAKE", current_step="FAILED")

    with pytest.raises(KeyError):
        await mem_repo.submit_human_review("APP-FAKE", approved=True, notes="")

    # En PostgresUnderwritingRepository
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        pg_repo = PostgresUnderwritingRepository(session)
        with pytest.raises(KeyError):
            await pg_repo.update_snapshot("APP-FAKE", current_step="FAILED")

        with pytest.raises(KeyError):
            await pg_repo.submit_human_review("APP-FAKE", approved=True, notes="")

    await test_engine.dispose()
