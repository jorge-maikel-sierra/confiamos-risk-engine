"""Middleware de Manejo de Errores conforme al Estándar RFC 7807 (Problem Details).

Garantiza respuestas de error uniformes con Content-Type: application/problem+json,
manteniendo retrocompatibilidad con el campo 'detail' para clientes legacy y Next.js.
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from src.application.exceptions import (
    ApplicationConflictError,
    ApplicationNotFoundError,
)
from src.domain.document_ingestion import (
    CorruptedDocumentError,
    PayloadTooLargeError,
    UnsupportedFileTypeError,
)


def create_problem_response(
    status_code: int,
    title: str,
    detail: str,
    error_type: str = "about:blank",
    instance: str | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    """Construye un JSONResponse conforme a RFC 7807 Problem Details."""
    body: dict[str, Any] = {
        "type": error_type,
        "title": title,
        "status": status_code,
        "detail": detail,
    }
    if instance:
        body["instance"] = instance
    if extra:
        body.update(extra)

    return JSONResponse(
        status_code=status_code,
        content=body,
        media_type="application/problem+json",
    )


def register_problem_details_handlers(app: FastAPI) -> None:
    """Registra los manejadores de excepciones estándar en la aplicación FastAPI."""

    @app.exception_handler(ApplicationNotFoundError)
    async def not_found_handler(request: Request, exc: ApplicationNotFoundError) -> JSONResponse:
        return create_problem_response(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Recurso No Encontrado",
            detail=exc.message,
            error_type="https://confiamos.co/errors/not-found",
            instance=request.url.path,
            extra={"code": exc.code, "application_id": exc.application_id},
        )

    @app.exception_handler(ApplicationConflictError)
    async def conflict_handler(request: Request, exc: ApplicationConflictError) -> JSONResponse:
        return create_problem_response(
            status_code=status.HTTP_409_CONFLICT,
            title="Conflicto de Estado",
            detail=exc.message,
            error_type="https://confiamos.co/errors/conflict",
            instance=request.url.path,
            extra={"code": exc.code, "application_id": exc.application_id},
        )

    @app.exception_handler(UnsupportedFileTypeError)
    async def unsupported_file_handler(
        request: Request, exc: UnsupportedFileTypeError
    ) -> JSONResponse:
        return create_problem_response(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            title="Tipo de Archivo No Soportado",
            detail=str(exc),
            error_type="https://confiamos.co/errors/unsupported-media-type",
            instance=request.url.path,
        )

    @app.exception_handler(PayloadTooLargeError)
    async def payload_too_large_handler(
        request: Request, exc: PayloadTooLargeError
    ) -> JSONResponse:
        return create_problem_response(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            title="Archivo Demasiado Grande",
            detail=str(exc),
            error_type="https://confiamos.co/errors/content-too-large",
            instance=request.url.path,
        )

    @app.exception_handler(CorruptedDocumentError)
    async def corrupted_document_handler(
        request: Request, exc: CorruptedDocumentError
    ) -> JSONResponse:
        return create_problem_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            title="Documento Inválido o Dañado",
            detail=str(exc),
            error_type="https://confiamos.co/errors/unprocessable-document",
            instance=request.url.path,
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return create_problem_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Regla de Negocio Incumplida",
            detail=str(exc),
            error_type="https://confiamos.co/errors/business-rule-violation",
            instance=request.url.path,
        )

