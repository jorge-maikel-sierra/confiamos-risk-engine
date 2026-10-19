"""Configuración y conexión asíncrona a la base de datos (SPEC-02).

Provee:
- Motor asíncrono SQLAlchemy (`create_async_engine`)
- Factoría de sesiones (`async_sessionmaker`)
- Declarative Base para modelos ORM
- Inyector de dependencias `get_db_session`
"""

import os
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Clase base declarativa para todos los modelos ORM de la cooperativa."""

    pass


def get_database_url() -> str:
    """Resuelve la URL asíncrona de base de datos a partir del entorno."""
    raw_url = os.getenv(
        "DATABASE_URL",
        "postgresql://confiamos_user:confiamos_password@localhost:5432/confiamos_risk_db",
    )
    # Adaptar prefijo para el driver asíncrono asyncpg si es postgresql://
    if raw_url.startswith("postgresql://"):
        return raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
    return raw_url


def create_engine_and_sessionmaker(
    database_url: str | None = None,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Crea una tupla con el motor asíncrono y la factoría de sesiones."""
    url = database_url or get_database_url()

    # Si es SQLite en memoria o testing
    engine_kwargs: dict[str, Any] = {"echo": False}
    if url.startswith("postgresql"):
        engine_kwargs["pool_pre_ping"] = True
        engine_kwargs["pool_size"] = 10
        engine_kwargs["max_overflow"] = 20

    engine = create_async_engine(url, **engine_kwargs)
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    return engine, session_factory


# Instancias por defecto para la aplicación
engine, async_session_factory = create_engine_and_sessionmaker()


async def init_db(target_engine: AsyncEngine | None = None) -> None:
    """Crea las tablas declarativas y habilita pgvector si no existen en la base de datos."""
    import src.infrastructure.models  # noqa: F401

    eng = target_engine or engine
    async with eng.begin() as conn:
        if eng.dialect.name == "postgresql":
            from sqlalchemy import text

            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await conn.execute(
                text("ALTER TABLE credit_applications ADD COLUMN IF NOT EXISTS scorecard JSONB;")
            )
            await conn.execute(
                text(
                    "ALTER TABLE credit_applications ADD COLUMN IF NOT EXISTS "
                    "historical_precedents JSONB;"
                )
            )
        await conn.run_sync(Base.metadata.create_all)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Generador de dependencias de FastAPI para inyectar AsyncSession en rutas."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
