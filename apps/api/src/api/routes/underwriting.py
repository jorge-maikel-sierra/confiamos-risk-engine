"""Controlador HTTP REST (Driving Adapter) para suscripción crediticia (Arquitectura Hexagonal).

Cumple estrictamente con:
- Responsabilidad Única (SRP): Solo traduce peticiones HTTP hacia Casos de Uso.
- Inversión de Dependencias (DIP): Inyecta Casos de Uso provistos por el Composition Root.
- Estándares HTTP REST (RFC 9110): Location en 201 Created, Cache-Control y Problem Details.
"""

import asyncio
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse

from src.api.container import (
    get_export_dossier_pdf_use_case,
    get_export_financial_excel_use_case,
    get_get_stress_test_analysis_use_case,
    get_ingest_document_use_case,
    get_list_underwritings_use_case,
    get_risk_auditor,
    get_start_underwriting_use_case,
    get_stress_test_underwriting_use_case,
    get_submit_human_review_use_case,
    get_underwriting_by_id_use_case,
    get_underwriting_repository,
    get_verify_integrity_seal_use_case,
)
from src.api.schemas import (
    HistoricalPrecedentSchema,
    HumanReviewRequestSchema,
    MetricsSummarySchema,
    PaginatedUnderwritingListSchema,
    StressTestRequestSchema,
    UnderwriteRequestSchema,
    UnderwriteResponseSchema,
)
from src.application.use_cases.export_dossier import (
    ExportDossierPdfUseCase,
    ExportFinancialExcelUseCase,
    VerifyIntegritySealUseCase,
)
from src.application.use_cases.get_underwriting import (
    GetUnderwritingByIdUseCase,
    ListUnderwritingsQuery,
    ListUnderwritingsUseCase,
)
from src.application.use_cases.ingest_document import (
    IngestDocumentCommand,
    IngestFinancialDocumentUseCase,
)
from src.application.use_cases.start_underwriting import (
    StartUnderwritingCommand,
    StartUnderwritingUseCase,
)
from src.application.use_cases.stress_test_underwriting import (
    GetStressTestAnalysisUseCase,
    StressTestUnderwritingUseCase,
)
from src.application.use_cases.submit_human_review import (
    SubmitHumanReviewCommand,
    SubmitHumanReviewUseCase,
)
from src.domain.document_ingestion import FinancialExtractionResult
from src.domain.scoring import CreditScorecardResult
from src.domain.stress_testing import StressTestingAnalysis
from src.infrastructure.aws_sns_adapter import global_event_broadcaster
from src.infrastructure.observability import get_observability_tracker

# Re-exports para retrocompatibilidad con tests existentes
__all__ = [
    "get_observability_tracker",
    "get_risk_auditor",
    "get_underwriting_repository",
    "stream_underwriting_events",
    "router",
]

router = APIRouter(tags=["Credit Underwriting"])


def _format_underwrite_response(app_id: str, values: dict[str, Any]) -> UnderwriteResponseSchema:
    """Convierte el diccionario de valores o entidad relacional en el esquema de respuesta."""
    metrics_summary = None
    metrics_obj = values.get("metrics")
    if metrics_obj:
        if isinstance(metrics_obj, dict):
            dscr_val = metrics_obj.get("dscr")
            if dscr_val is None and "dscr_result" in metrics_obj:
                dscr_val = metrics_obj["dscr_result"].get("dscr")

            is_solvent = metrics_obj.get("is_solvent", False)
            if "dscr_result" in metrics_obj:
                is_solvent = metrics_obj["dscr_result"].get("is_solvent", False)

            is_debt_free = metrics_obj.get("is_debt_free", False)
            if "dscr_result" in metrics_obj:
                is_debt_free = metrics_obj["dscr_result"].get("is_debt_free", False)

            metrics_summary = MetricsSummarySchema(
                dscr=dscr_val,
                current_ratio=metrics_obj.get("current_ratio"),
                runway_months=metrics_obj.get("runway_months"),
                is_solvent=is_solvent,
                is_debt_free=is_debt_free,
                anomaly_flags=metrics_obj.get("anomaly_flags", []),
            )
        else:
            metrics_summary = MetricsSummarySchema(
                dscr=metrics_obj.dscr_result.dscr,
                current_ratio=metrics_obj.current_ratio,
                runway_months=metrics_obj.runway_months,
                is_solvent=metrics_obj.dscr_result.is_solvent,
                is_debt_free=metrics_obj.dscr_result.is_debt_free,
                anomaly_flags=metrics_obj.anomaly_flags,
            )

    historical_precedents: list[HistoricalPrecedentSchema] = []
    raw_precs = values.get("historical_precedents") or []
    for item in raw_precs:
        if isinstance(item, HistoricalPrecedentSchema):
            historical_precedents.append(item)
        elif isinstance(item, dict):
            historical_precedents.append(HistoricalPrecedentSchema(**item))
        elif hasattr(item, "to_dict"):
            historical_precedents.append(HistoricalPrecedentSchema(**item.to_dict()))

    scorecard_res = None
    raw_scorecard = values.get("scorecard")
    if raw_scorecard:
        if isinstance(raw_scorecard, CreditScorecardResult):
            scorecard_res = raw_scorecard
        elif isinstance(raw_scorecard, dict):
            scorecard_res = CreditScorecardResult(**raw_scorecard)

    stress_res = None
    raw_stress = values.get("stress_test_results")
    if raw_stress:
        if isinstance(raw_stress, StressTestingAnalysis):
            stress_res = raw_stress
        elif isinstance(raw_stress, dict):
            stress_res = StressTestingAnalysis(**raw_stress)

    return UnderwriteResponseSchema(
        application_id=app_id,
        associated_id=values.get("associated_id", ""),
        business_name=values.get("business_name", ""),
        sector=values.get("sector") or "Comercio y Servicios",
        current_step=values.get("current_step", "INITIALIZED"),
        is_completed=values.get("is_completed", False),
        metrics=metrics_summary,
        ai_verdict=values.get("ai_verdict"),
        scorecard=scorecard_res,
        historical_precedents=historical_precedents,
        stress_test_results=stress_res,
        human_approved=values.get("human_approved"),
        human_notes=values.get("human_notes"),
        errors=values.get("errors", []),
        created_at=str(values.get("created_at")) if values.get("created_at") else None,
        updated_at=str(values.get("updated_at")) if values.get("updated_at") else None,
    )


# -------------------------------------------------------------------------
# Endpoints HTTP REST (Driving Adapters)
# -------------------------------------------------------------------------


@router.post(
    "",
    response_model=UnderwriteResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Iniciar evaluación crediticia",
    description="Persiste la solicitud y ejecuta el flujo determinístico hasta la pausa de comité.",
)
async def start_underwriting(
    payload: UnderwriteRequestSchema,
    response: Response,
    use_case: Annotated[StartUnderwritingUseCase, Depends(get_start_underwriting_use_case)],
) -> UnderwriteResponseSchema:
    command = StartUnderwritingCommand(
        associated_id=payload.associated_id,
        business_name=payload.business_name,
        requested_amount_usd=payload.requested_amount_usd,
        term_months=payload.term_months,
        financial_data=payload.financial_data.model_dump(),
        sector=payload.sector,
    )

    record = await use_case.execute(command)
    app_id = record["application_id"]

    # Cumplimiento RFC 9110: Header Location obligatorio en 201 Created
    response.headers["Location"] = f"/api/v1/underwritings/{app_id}"

    return _format_underwrite_response(app_id, record)


@router.get(
    "",
    response_model=PaginatedUnderwritingListSchema,
    summary="Bandeja de solicitudes de crédito",
    description="Retorna la lista paginada de solicitudes con opción de filtrado por estado.",
)
async def list_underwritings(
    use_case: Annotated[ListUnderwritingsUseCase, Depends(get_list_underwritings_use_case)],
    limit: int = Query(default=20, ge=1, le=100, description="Cantidad máxima de registros"),
    offset: int = Query(default=0, ge=0, description="Desplazamiento inicial"),
    status_filter: str | None = Query(
        default=None, alias="status", description="Filtrar por estado del workflow"
    ),
) -> PaginatedUnderwritingListSchema:
    query = ListUnderwritingsQuery(limit=limit, offset=offset, status_filter=status_filter)
    records, total = await use_case.execute(query)

    items = [_format_underwrite_response(r["application_id"], r) for r in records]
    return PaginatedUnderwritingListSchema(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/events",
    summary="Canal de eventos en tiempo real (Server-Sent Events)",
    description="Transmite eventos del motor crediticio hacia el frontend mediante SSE.",
)
@router.get(
    "/events/sse",
    include_in_schema=False,
)
async def stream_underwriting_events() -> StreamingResponse:
    queue = global_event_broadcaster.create_subscription()

    async def event_generator():
        try:
            yield ": ping\n\n"
            while True:
                event = await queue.get()
                yield event.to_sse_message()
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            global_event_broadcaster.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/upload-financials",
    response_model=FinancialExtractionResult,
    status_code=status.HTTP_200_OK,
    summary="Ingesta documental y extracción financiera (SPEC-08)",
    description="Valida magic bytes y extrae balances mediante Gemini Vision o Excel parser.",
)
async def upload_financials(
    file: Annotated[UploadFile, File(description="Archivo de estados financieros (PDF o XLSX)")],
    use_case: Annotated[IngestFinancialDocumentUseCase, Depends(get_ingest_document_use_case)],
) -> FinancialExtractionResult:
    content = await file.read()
    command = IngestDocumentCommand(
        file_bytes=content,
        filename=file.filename or "documento_adjunto",
    )
    return await use_case.execute(command)


@router.get(
    "/{application_id}",
    response_model=UnderwriteResponseSchema,
    summary="Consultar estado de la solicitud",
    description="Retorna el snapshot persistido de la evaluación crediticia.",
)
async def get_underwriting_status(
    application_id: str,
    use_case: Annotated[GetUnderwritingByIdUseCase, Depends(get_underwriting_by_id_use_case)],
) -> UnderwriteResponseSchema:
    record = await use_case.execute(application_id)
    return _format_underwrite_response(application_id, record)


@router.post(
    "/{application_id}/review",
    response_model=UnderwriteResponseSchema,
    include_in_schema=False,
)
@router.post(
    "/{application_id}/reviews",
    response_model=UnderwriteResponseSchema,
    summary="Emitir resolución del oficial de crédito",
    description="Reanuda la ejecución del StateGraph y persiste la resolución en base de datos.",
)
async def submit_human_review(
    application_id: str,
    payload: HumanReviewRequestSchema,
    use_case: Annotated[SubmitHumanReviewUseCase, Depends(get_submit_human_review_use_case)],
) -> UnderwriteResponseSchema:
    command = SubmitHumanReviewCommand(
        application_id=application_id,
        approved=payload.approved,
        notes=payload.notes,
    )
    updated_record = await use_case.execute(command)
    return _format_underwrite_response(application_id, updated_record)


@router.get(
    "/{application_id}/export/pdf",
    summary="Exportar dictamen formal en PDF bancario",
    description="Genera el acta oficial de dictamen crediticio con sello criptográfico SHA-256.",
)
async def export_pdf(
    application_id: str,
    use_case: Annotated[ExportDossierPdfUseCase, Depends(get_export_dossier_pdf_use_case)],
) -> Response:
    pdf_bytes, filename = await use_case.execute(application_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store, private",
        },
    )


@router.get(
    "/{application_id}/export/excel",
    summary="Exportar planilla de trabajo financiero en Excel (.xlsx)",
    description="Genera el libro de cálculo financiero con fórmulas vivas de liquidez y cobertura.",
)
async def export_excel(
    application_id: str,
    use_case: Annotated[ExportFinancialExcelUseCase, Depends(get_export_financial_excel_use_case)],
) -> Response:
    excel_bytes, filename = await use_case.execute(application_id)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store, private",
        },
    )


@router.get(
    "/{application_id}/verify-seal",
    summary="Verificar autenticidad del sello criptográfico",
    description="Calcula el hash canónico actual y lo compara contra el hash proporcionado.",
)
async def verify_seal(
    application_id: str,
    use_case: Annotated[VerifyIntegritySealUseCase, Depends(get_verify_integrity_seal_use_case)],
    hash: str | None = Query(default=None, description="Hash SHA-256 a validar"),
) -> dict[str, Any]:
    result = await use_case.execute(application_id=application_id, provided_hash=hash)
    return {
        "application_id": result.application_id,
        "expected_hash": result.expected_hash,
        "provided_hash": result.provided_hash,
        "is_authentic": result.is_authentic,
        "verified_at": result.verified_at,
    }


@router.post(
    "/{application_id}/stress-test",
    response_model=StressTestingAnalysis,
    summary="Simular pruebas de estrés financiero y sensibilidad",
    description="Calcula el impacto determinístico de choques de ventas, costos y tasa de interés (SPEC-10).",
)
async def run_stress_test(
    application_id: str,
    payload: StressTestRequestSchema | None = None,
    use_case: Annotated[
        StressTestUnderwritingUseCase, Depends(get_stress_test_underwriting_use_case)
    ] = None,
) -> StressTestingAnalysis:
    custom = payload.custom_scenario if payload else None
    return await use_case.execute(application_id=application_id, custom_scenario=custom)


@router.get(
    "/{application_id}/stress-test",
    response_model=StressTestingAnalysis,
    summary="Consultar análisis de estrés financiero",
    description="Retorna el análisis de estrés financiero previamente simulado o lo calcula on-demand.",
)
async def get_stress_test(
    application_id: str,
    use_case: Annotated[
        GetStressTestAnalysisUseCase, Depends(get_get_stress_test_analysis_use_case)
    ] = None,
) -> StressTestingAnalysis:
    return await use_case.execute(application_id=application_id)

