"""Confiamos Risk Engine (CRE) - API Entrypoint."""

from fastapi import FastAPI

app = FastAPI(
    title="Confiamos Risk Engine (CRE)",
    description=(
        "Motor determinístico y asistido por IA para evaluación crediticia de "
        "Cooperativa Confiamos."
    ),
    version="1.0.0",
)


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Endpoint de verificación de estado del servicio."""
    return {
        "status": "healthy",
        "service": "confiamos-risk-engine-api",
        "version": "1.0.0",
    }
