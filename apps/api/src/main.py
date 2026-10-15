"""Confiamos Risk Engine (CRE) - API Entrypoint (SPEC-01 y SPEC-02)."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from src.api.routes.underwriting import router as underwriting_router
from src.infrastructure.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Ciclo de vida de la aplicación: inicializa esquemas relacionales en arranque."""
    try:
        await init_db()
    except Exception:
        # Modo resiliente ante ausencia de base de datos en testing o arranque frío
        pass
    yield


app = FastAPI(
    title="Confiamos Risk Engine (CRE)",
    description=(
        "Motor determinístico y asistido por IA para evaluación crediticia de "
        "Cooperativa Confiamos."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Ruta canónica en plural conforme al estándar estricto de APIs REST (FreeCodeCamp)
app.include_router(underwriting_router, prefix="/api/v1/underwritings")

# Ruta retrocompatible para SPEC-01
app.include_router(underwriting_router, prefix="/api/v1/underwrite", include_in_schema=False)


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Endpoint de verificación de estado del servicio."""
    return {
        "status": "healthy",
        "service": "confiamos-risk-engine-api",
        "version": "1.0.0",
    }
