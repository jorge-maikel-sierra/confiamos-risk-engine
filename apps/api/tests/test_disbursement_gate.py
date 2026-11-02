"""Tests unitarios y de integración para la Compuerta de Desembolso y Pagaré Digital (SPEC-14).

Cubre los criterios de aceptación formales TEST-01 a TEST-06:
- TEST-01: Bloqueo estricto de desembolso ante covenants precedentes pendientes.
- TEST-02: Verificación unitaria y levantamiento de covenants con trazabilidad.
- TEST-03: Cálculo matemático exacto de liquidación neta cooperativa (Aportes 2%, Fondo $25, Seguro).
- TEST-04: Emisión determinística de Pagaré Desmaterializado (PAGARE-2026-XXXX).
- TEST-05: Ejecución de giro, transición de estado a DISBURSED y cierre de expediente.
- TEST-06: Endpoints HTTP REST, Problem Details (RFC 7807) ante 409 Conflict y persistencia.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.application.exceptions import ApplicationConflictError
from src.application.use_cases.manage_disbursement import (
    ExecuteDisbursementUseCase,
    GetDisbursementGateStatusUseCase,
    VerifyCovenantUseCase,
)
from src.domain.committee import (
    ApprovalAuthorityLevel,
    CommitteeResolution,
    CreditCovenant,
    ResolutionStatus,
)
from src.domain.disbursement import (
    CovenantFulfillmentRecord,
    CovenantFulfillmentStatus,
    DisbursementEngine,
)
from src.infrastructure.repositories import InMemoryUnderwritingRepository
from src.main import app


def test_01_disbursement_gate_strict_blocking() -> None:
    """TEST-01: Bloqueo estricto de desembolso ante covenants precedentes pendientes o falta de aprobación."""
    # Caso 1: Expediente en deliberación (No aprobado aún)
    eligible_1, reasons_1 = DisbursementEngine.evaluate_gate(
        resolution_status="IN_DELIBERATION",
        covenants=[],
    )
    assert eligible_1 is False
    assert any("no cuenta con aprobación formal" in r for r in reasons_1)

    # Caso 2: Aprobado con condiciones, pero con 1 covenant en estado PENDING
    pending_cov = CovenantFulfillmentRecord(
        code="COV-HIP-01",
        description="Hipoteca en primer grado debidamente registrada.",
        status=CovenantFulfillmentStatus.PENDING,
    )
    eligible_2, reasons_2 = DisbursementEngine.evaluate_gate(
        resolution_status="APPROVED_WITH_CONDITIONS",
        covenants=[pending_cov],
    )
    assert eligible_2 is False
    assert any("1 condición(es) precedente(s) pendiente(s)" in r for r in reasons_2)

    # Caso 3: Aprobado con condiciones y covenant debidamente FULFILLED
    fulfilled_cov = pending_cov.model_copy(update={"status": CovenantFulfillmentStatus.FULFILLED})
    eligible_3, reasons_3 = DisbursementEngine.evaluate_gate(
        resolution_status="APPROVED_WITH_CONDITIONS",
        covenants=[fulfilled_cov],
    )
    assert eligible_3 is True
    assert len(reasons_3) == 0

    # Caso 4: Expediente ya desembolsado previamente
    eligible_4, reasons_4 = DisbursementEngine.evaluate_gate(
        resolution_status="APPROVED_BY_COMMITTEE",
        covenants=[],
        is_already_disbursed=True,
    )
    assert eligible_4 is False
    assert any("ya fue desembolsado" in r for r in reasons_4)


@pytest.mark.asyncio
async def test_02_covenant_verification_and_lifting() -> None:
    """TEST-02: Verificación unitaria y levantamiento de covenants con trazabilidad y auditoría."""
    repo = InMemoryUnderwritingRepository()
    app_id = "APP-TEST-COV-01"

    # Crear expediente en memoria
    await repo.create_application(
        application_id=app_id,
        associated_id="ASOC-1001",
        business_name="Distribuidora del Sur S.A.S.",
        requested_amount_usd=40000.0,
        term_months=24,
        raw_financials={},
    )

    # Asignar acta de comité aprobada con dos covenants
    resolution = CommitteeResolution(
        application_id=app_id,
        act_number="ACTA-2026-0001",
        governance_level=ApprovalAuthorityLevel.LEVEL_2_MANAGER,
        governance_title="Gerencia de Crédito",
        status=ResolutionStatus.APPROVED_WITH_CONDITIONS,
        required_quorum=2,
        votes_cast_count=2,
        is_quorum_reached=True,
        votes=[],
        approved_covenants=[
            CreditCovenant(
                code="COV-POL-01",
                description="Póliza todo riesgo endosada a la cooperativa.",
                covenant_type="GARANTIA",
                due_days=15,
            ),
            CreditCovenant(
                code="COV-BAL-02",
                description="Estados financieros certificados del último trimestre.",
                covenant_type="DOCUMENTAL",
                due_days=30,
            ),
        ],
        resolution_notes="Aprobado sujeto al levantamiento de ambas condiciones.",
        is_final=True,
    )
    await repo.save_committee_resolution(
        application_id=app_id,
        resolution=resolution.model_dump(),
        is_final=True,
    )

    gate_use_case = GetDisbursementGateStatusUseCase(repository=repo)
    verify_use_case = VerifyCovenantUseCase(repository=repo, get_gate_status_use_case=gate_use_case)

    # Estado inicial: ambos pendientes
    status_init = await gate_use_case.execute(app_id)
    assert status_init.is_eligible is False
    assert status_init.pending_covenants_count == 2

    # Verificar primer covenant (COV-POL-01)
    status_step1 = await verify_use_case.execute(
        application_id=app_id,
        code="COV-POL-01",
        verified_by="USR-OFICIAL-01",
        notes="Póliza #883921 radicada con recibo de prima cancelada.",
        status=CovenantFulfillmentStatus.FULFILLED,
    )
    assert status_step1.is_eligible is False
    assert status_step1.pending_covenants_count == 1
    cov_1 = next(c for c in status_step1.covenants if c.code == "COV-POL-01")
    assert cov_1.status == CovenantFulfillmentStatus.FULFILLED
    assert cov_1.verified_by == "USR-OFICIAL-01"
    assert cov_1.evidence_notes is not None

    # Exonerar/Verificar segundo covenant (COV-BAL-02 como WAIVED por junta)
    status_step2 = await verify_use_case.execute(
        application_id=app_id,
        code="COV-BAL-02",
        verified_by="USR-GERENTE-02",
        notes="Exonerado por presentar balance dictaminado semestral.",
        status=CovenantFulfillmentStatus.WAIVED,
    )
    assert status_step2.is_eligible is True
    assert status_step2.pending_covenants_count == 0


def test_03_cooperative_liquidation_math() -> None:
    """TEST-03: Cálculo matemático exacto de liquidación cooperativa con deducciones reglamentarias."""
    gross_amount = 50000.0
    monthly_insurance_rate = 0.0012  # 0.12% mensual

    liquidation = DisbursementEngine.calculate_liquidation(
        gross_amount_usd=gross_amount,
        monthly_insurance_rate=monthly_insurance_rate,
    )

    # Verificación de fórmulas estatutarias
    assert liquidation.gross_amount_usd == 50000.0
    assert liquidation.social_contributions_pct == 2.0
    assert liquidation.social_contributions_usd == 1000.0  # 50000 * 2.0%
    assert liquidation.solidarity_fund_usd == 25.0  # Cuota fija de auxilio
    assert liquidation.insurance_first_month_usd == 60.0  # 50000 * 0.12%
    assert liquidation.total_deductions_usd == 1085.0  # 1000 + 25 + 60
    assert liquidation.net_disbursement_usd == 48915.0  # 50000 - 1085


def test_04_digital_promissory_note_generation() -> None:
    """TEST-04: Emisión determinística de Pagaré Desmaterializado con cláusula aceleratoria."""
    promissory_note = DisbursementEngine.create_promissory_note(
        debtor_name="Industrias Metálicas del Norte S.A.S.",
        debtor_id="NIT-900882194-1",
        principal_amount_usd=75000.0,
        applied_tea=17.85,
        term_months=36,
    )

    assert promissory_note.note_number.startswith("PAGARE-2026-")
    assert promissory_note.debtor_name == "Industrias Metálicas del Norte S.A.S."
    assert promissory_note.debtor_id == "NIT-900882194-1"
    assert promissory_note.principal_amount_usd == 75000.0
    assert promissory_note.applied_tea == 17.85
    assert promissory_note.term_months == 36
    assert promissory_note.acceleration_clause_accepted is True
    assert promissory_note.issued_at is not None
    assert promissory_note.maturity_date is not None


@pytest.mark.asyncio
async def test_05_disbursement_execution_and_status_transition() -> None:
    """TEST-05: Ejecución de giro, transición de estado a DISBURSED y cierre definitivo de expediente."""
    repo = InMemoryUnderwritingRepository()
    app_id = "APP-TEST-EXEC-01"

    await repo.create_application(
        application_id=app_id,
        associated_id="ASOC-2002",
        business_name="Soluciones Médicas S.A.",
        requested_amount_usd=25000.0,
        term_months=12,
        raw_financials={},
    )

    # Acta aprobada sin covenants
    resolution = CommitteeResolution(
        application_id=app_id,
        act_number="ACTA-2026-0002",
        governance_level=ApprovalAuthorityLevel.LEVEL_1_OFFICER,
        status=ResolutionStatus.APPROVED_BY_COMMITTEE,
        required_quorum=1,
        votes_cast_count=1,
        is_quorum_reached=True,
        votes=[],
        approved_covenants=[],
        resolution_notes="Aprobado directamente sin condiciones.",
        is_final=True,
    )
    await repo.save_committee_resolution(
        application_id=app_id,
        resolution=resolution.model_dump(),
        is_final=True,
    )

    gate_use_case = GetDisbursementGateStatusUseCase(repository=repo)
    exec_use_case = ExecuteDisbursementUseCase(repository=repo, get_gate_status_use_case=gate_use_case)

    # Ejecutar desembolso
    order = await exec_use_case.execute(
        application_id=app_id,
        destination_bank="Bancolombia",
        destination_account_number="241-998341-02",
        account_type="AHORROS",
    )

    assert order.order_id.startswith("GIRO-2026-")
    assert order.application_id == app_id
    assert order.destination_bank == "Bancolombia"
    assert order.destination_account_number == "241-998341-02"
    assert order.status == "EXECUTED"
    assert order.liquidation.gross_amount_usd == 25000.0
    assert order.promissory_note.note_number.startswith("PAGARE-2026-")

    # Verificar expediente en persistencia
    updated_rec = await repo.get_by_id(app_id)
    assert updated_rec is not None
    assert updated_rec["current_step"] == "DISBURSED"
    assert updated_rec["is_completed"] is True
    assert updated_rec["disbursement_order"] is not None

    # Intentar ejecutar nuevamente debe fallar con ApplicationConflictError
    with pytest.raises(ApplicationConflictError) as exc_info:
        await exec_use_case.execute(
            application_id=app_id,
            destination_bank="Bancolombia",
            destination_account_number="241-998341-02",
        )
    assert "bloqueado por la compuerta" in exc_info.value.message


@pytest.mark.asyncio
async def test_06_http_rest_disbursement_flow_and_rfc7807() -> None:
    """TEST-06: Endpoints HTTP REST, ciclo completo de desembolso y Problem Details RFC 7807."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # 1. Crear solicitud crediticia inicial
        init_payload = {
            "associated_id": "ASOC-REST-01",
            "business_name": "Tecnología y Redes del Café S.A.S.",
            "sector": "Servicios Tecnológicos",
            "requested_amount_usd": 60000.0,
            "term_months": 24,
            "financial_data": {
                "operating_cash_flow": 80000.0,
                "annual_debt_service": 20000.0,
                "current_assets": 120000.0,
                "current_liabilities": 50000.0,
                "cash_balance": 40000.0,
                "monthly_burn_rate": 6000.0,
                "negative_balance_days": 0,
                "top_client_revenue_percentage": 20.0,
            },
        }
        res_create = await client.post("/api/v1/underwritings", json=init_payload)
        assert res_create.status_code == 201
        app_id = res_create.json()["application_id"]

        # 2. Consultar compuerta antes de sesionar en comité -> Debe indicar no elegible
        res_gate_init = await client.get(f"/api/v1/underwritings/{app_id}/disbursement")
        assert res_gate_init.status_code == 200
        gate_init_data = res_gate_init.json()
        assert gate_init_data["is_eligible"] is False
        assert "no cuenta con aprobación" in gate_init_data["blocking_reasons"][0]

        # 3. Intentar desembolsar sin aprobación -> Debe retornar 409 Conflict (RFC 7807)
        res_exec_fail = await client.post(
            f"/api/v1/underwritings/{app_id}/disbursement/execute",
            json={
                "destination_bank": "Banco de Bogotá",
                "destination_account_number": "100-293847-11",
                "account_type": "CORRIENTE",
            },
        )
        assert res_exec_fail.status_code == 409
        prob_409 = res_exec_fail.json()
        assert prob_409["status"] == 409
        assert "Conflicto" in prob_409["title"]
        assert "bloqueado por la compuerta" in prob_409["detail"]

        # 4. Aprobar en comité con una condición precedente (COV-SEGURO-01)
        res_vote_1 = await client.post(
            f"/api/v1/underwritings/{app_id}/committee/votes",
            json={
                "voter_id": "USR-OFICIAL-01",
                "voter_name": "Andrés Riesgos",
                "role": "RISK_OFFICER",
                "vote": "CONDITION",
                "notes": "Aprobado condicionado a entrega de seguro vehicular.",
                "covenants": [
                    {
                        "code": "COV-SEGURO-01",
                        "description": "Póliza de seguro con cláusula de cesión de derechos.",
                        "covenant_type": "GARANTIA",
                        "due_days": 15,
                    }
                ],
            },
        )
        assert res_vote_1.status_code == 200

        res_vote_2 = await client.post(
            f"/api/v1/underwritings/{app_id}/committee/votes",
            json={
                "voter_id": "USR-GERENTE-02",
                "voter_name": "Marta Gerente",
                "role": "CREDIT_MANAGER",
                "vote": "APPROVE",
                "notes": "Voto aprobatorio mayoritario.",
                "covenants": [],
            },
        )
        assert res_vote_2.status_code == 200
        assert res_vote_2.json()["is_final"] is True

        # 5. Consultar compuerta -> Aprobada pero bloqueada por COV-SEGURO-01 pendiente
        res_gate_pending = await client.get(f"/api/v1/underwritings/{app_id}/disbursement")
        assert res_gate_pending.status_code == 200
        gate_pend_data = res_gate_pending.json()
        assert gate_pend_data["is_eligible"] is False
        assert gate_pend_data["pending_covenants_count"] == 1
        assert gate_pend_data["covenants"][0]["code"] == "COV-SEGURO-01"

        # 6. Levantar/Verificar la condición precedente vía POST
        res_verify = await client.post(
            f"/api/v1/underwritings/{app_id}/disbursement/covenants/COV-SEGURO-01/verify",
            json={
                "verified_by": "USR-OFICIAL-01",
                "notes": "Póliza radicada en ventanilla No. 44921.",
                "status": "FULFILLED",
            },
        )
        assert res_verify.status_code == 200
        gate_verified = res_verify.json()
        assert gate_verified["is_eligible"] is True
        assert gate_verified["pending_covenants_count"] == 0

        # 7. Ejecutar desembolso oficial vía POST /disbursement/execute
        res_disburse = await client.post(
            f"/api/v1/underwritings/{app_id}/disbursement/execute",
            json={
                "destination_bank": "Banco de Bogotá",
                "destination_account_number": "100-293847-11",
                "account_type": "CORRIENTE",
            },
        )
        assert res_disburse.status_code == 200
        order_data = res_disburse.json()
        assert order_data["order_id"].startswith("GIRO-2026-")
        assert order_data["promissory_note"]["note_number"].startswith("PAGARE-2026-")
        assert order_data["liquidation"]["gross_amount_usd"] == 60000.0
        assert order_data["liquidation"]["social_contributions_usd"] == 1200.0  # 2.0% de 60,000
        assert order_data["liquidation"]["solidarity_fund_usd"] == 25.0

        # 8. Verificar que el expediente refleje el estado DISBURSED en GET /{app_id}
        res_get_app = await client.get(f"/api/v1/underwritings/{app_id}")
        assert res_get_app.status_code == 200
        app_data = res_get_app.json()
        assert app_data["current_step"] == "DISBURSED"
        assert app_data["is_completed"] is True
        assert app_data["disbursement_order"] is not None
        assert app_data["disbursement_order"]["order_id"] == order_data["order_id"]

        # 9. Solicitud inexistente debe retornar 404 RFC 7807
        res_not_found = await client.get("/api/v1/underwritings/non-existent-id/disbursement")
        assert res_not_found.status_code == 404
        assert res_not_found.json()["status"] == 404
