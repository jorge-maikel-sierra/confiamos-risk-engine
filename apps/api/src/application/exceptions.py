"""Excepciones de la Capa de Aplicación (Arquitectura Hexagonal).

Mapean conceptos de error de negocio independientes del protocolo HTTP.
"""


class ApplicationError(Exception):
    """Excepción base para errores de aplicación."""

    def __init__(self, message: str, code: str = "APPLICATION_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class ApplicationNotFoundError(ApplicationError):
    """Se lanza cuando una solicitud crediticia no existe."""

    def __init__(self, application_id: str) -> None:
        super().__init__(
            message=f"No se encontró la solicitud '{application_id}'.",
            code="NOT_FOUND",
        )
        self.application_id = application_id


class ApplicationConflictError(ApplicationError):
    """Se lanza cuando se intenta realizar una acción inválida sobre el estado actual."""

    def __init__(self, application_id: str, reason: str) -> None:
        super().__init__(
            message=f"Conflicto en la solicitud '{application_id}': {reason}",
            code="CONFLICT",
        )
        self.application_id = application_id
        self.reason = reason


class DocumentProcessingError(ApplicationError):
    """Se lanza cuando ocurre un error procesando o validando un documento contable."""

    def __init__(self, message: str, code: str = "DOCUMENT_PROCESSING_ERROR") -> None:
        super().__init__(message=message, code=code)
