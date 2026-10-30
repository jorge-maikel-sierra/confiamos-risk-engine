"""Tests unitarios y de integración para la Matriz de Atribuciones y Comité de Crédito Colegiado (SPEC-13).

Cubre los criterios de aceptación formales TEST-01 a TEST-06:
- TEST-01: Determinación de nivel de gobernanza reglamentaria (Niveles 1 al 4).
- TEST-02: Registro de votos, seguimiento de quórum y prevención de voto duplicado.
- TEST-03: Aprobación colegiada por mayoría reglamentaria y emisión de Acta Oficial.
- TEST-04: Rechazo colegiado por mayoría de votos en contra.
- TEST-05: Inclusión de Covenants y resolución condicional (APPROVED_WITH_CONDITIONS).
- TEST-06: Endpoints HTTP REST GET/POST /committee/votes, persistencia y RFC 7807 ante 404/400.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.domain.committee import (
    ApprovalAuthorityLevel,
    CommitteeMemberRole,
    CommitteeVote,
    CommitteeVoteType,
    CreditCovenant,
    GovernanceEngine,
    ResolutionStatus,
)
from src.main import app


def test_01_governance_level_determination() -> None:
    """TEST-01: Determinación determinística del nivel de atribución según matriz estatutaria."""
    # Nivel 1: Oficial individual (Monto <= $15k, Rating A o B, LTV HEALTHY, sin usura)
    req_1 = GovernanceEngine.evaluate_required_level(
        application_id="APP-GOV-01",
        requested_amount_usd=12000.0,
        rating_category="A",
        ltv_status="HEALTHY",
        exceeds_usury_cap=False,
    )
    assert req_1.required_level == ApprovalAuthorityLevel.LEVEL_1_OFFICER
    assert req_1.required_quorum == 1
    assert CommitteeMemberRole.RISK_OFFICER in req_1.required_roles

    # Nivel 2: Gerencia de Crédito (Monto <= $40k o LTV Warning)
    req_2 = GovernanceEngine.evaluate_required_level(
        application_id="APP-GOV-02",
        requested_amount_usd=35000.0,
        rating_category="B",
        ltv_status="HEALTHY",
        exceeds_usury_cap=False,
    )
    assert req_2.required_level == ApprovalAuthorityLevel.LEVEL_2_MANAGER
    assert req_2.required_quorum == 2
    assert CommitteeMemberRole.CREDIT_MANAGER in req_2.required_roles

    # Nivel 3: Comité Colegiado (Monto <= $100k o Rating C)
    req_3 = GovernanceEngine.evaluate_required_level(
        application_id="APP-GOV-03",
        requested_amount_usd=75000.0,
        rating_category="C",
        ltv_status="HEALTHY",
        exceeds_usury_cap=False,
    )
    assert req_3.required_level == ApprovalAuthorityLevel.LEVEL_3_COMMITTEE
    assert req_3.required_quorum == 3
    assert CommitteeMemberRole.OPERATIONS_DIRECTOR in req_3.required_roles

    # Nivel 4: Consejo de Administración (Monto > $100k o Rating D/E o alerta de usura)
    req_4a = GovernanceEngine.evaluate_required_level(
        application_id="APP-GOV-04A",
        requested_amount_usd=150000.0,
        rating_category="A",
        ltv_status="HEALTHY",
        exceeds_usury_cap=False,
    )
    assert req_4a.required_level == ApprovalAuthorityLevel.LEVEL_4_BOARD
    assert req_4a.required_quorum == 3
    assert CommitteeMemberRole.BOARD_DIRECTOR in req_4a.required_roles

    req_4b = GovernanceEngine.evaluate_required_level(
        application_id="APP-GOV-04B",
        requested_amount_usd=20000.0,
        rating_category="D",
        ltv_status="HEALTHY",
        exceeds_usury_cap=False,
    )
    assert req_4b.required_level == ApprovalAuthorityLevel.LEVEL_4_BOARD


def test_02_vote_recording_quorum_and_duplicate_prevention() -> None:
    """TEST-02: Registro de votos, seguimiento de quórum y validación estricta contra votos duplicados."""
    req = GovernanceEngine.evaluate_required_level(
        application_id="APP-GOV-05",
        requested_amount_usd=60000.0,
        rating_category="B",
        ltv_status="HEALTHY",
        exceeds_usury_cap=False,
    )
    assert req.required_level == ApprovalAuthorityLevel.LEVEL_3_COMMITTEE
    assert req.required_quorum == 3

    # Voto 1: Oficial de Riesgo
    vote1 = CommitteeVote(
        voter_id="USR-01",
        voter_name="Carlos Riesgos",
        role=CommitteeMemberRole.RISK_OFFICER,
        vote=CommitteeVoteType.APPROVE,
        notes="Capacidad de pago verificada y métricas solventes.",
        voted_at="2026-10-30T10:00:00Z",
    )
    res1 = GovernanceEngine.tally_resolution(req, [], vote1)
    assert res1.status == ResolutionStatus.IN_DELIBERATION
    assert res1.is_final is False
    assert len(res1.votes) == 1
    assert res1.is_quorum_reached is False

    # Intento de voto duplicado por el mismo miembro debe lanzar ValueError
    duplicate_vote = CommitteeVote(
        voter_id="USR-01",
        voter_name="Carlos Riesgos",
        role=CommitteeMemberRole.RISK_OFFICER,
        vote=CommitteeVoteType.REJECT,
        notes="Cambio de opinión.",
        voted_at="2026-10-30T10:05:00Z",
    )
    with pytest.raises(ValueError, match="ya ha emitido su voto"):
        GovernanceEngine.tally_resolution(req, res1.votes, duplicate_vote)


def test_03_collegiate_approval_and_act_issuance() -> None:
    """TEST-03: Aprobación colegiada por mayoría calificada y generación de Acta Resolutiva Oficial."""
    req = GovernanceEngine.evaluate_required_level(
        application_id="APP-GOV-06",
        requested_amount_usd=50000.0,
        rating_category="B",
        ltv_status="HEALTHY",
        exceeds_usury_cap=False,
    )
    # Quórum 3, Mayoría 2
    vote1 = CommitteeVote(
        voter_id="USR-01",
        voter_name="Carlos Riesgos",
        role=CommitteeMemberRole.RISK_OFFICER,
        vote=CommitteeVoteType.APPROVE,
        notes="Aprobado por métricas financieras favorables.",
        voted_at="2026-10-30T10:00:00Z",
    )
    res1 = GovernanceEngine.tally_resolution(req, [], vote1)

    vote2 = CommitteeVote(
        voter_id="USR-02",
        voter_name="Laura Gerente",
        role=CommitteeMemberRole.CREDIT_MANAGER,
        vote=CommitteeVoteType.APPROVE,
        notes="Concurro con la aprobación técnica.",
        voted_at="2026-10-30T10:02:00Z",
    )
    res2 = GovernanceEngine.tally_resolution(req, res1.votes, vote2)

    # Con 2 votos favorables de 3 se alcanza la mayoría calificada
    assert res2.status == ResolutionStatus.APPROVED_BY_COMMITTEE
    assert res2.is_final is True
    assert res2.is_quorum_reached is True
    assert res2.act_number is not None
    assert res2.act_number.startswith("ACTA-")
    assert "Resolución favorable adoptada" in res2.resolution_notes


def test_04_collegiate_rejection_by_majority() -> None:
    """TEST-04: Rechazo colegiado por mayoría de votos en contra."""
    req = GovernanceEngine.evaluate_required_level(
        application_id="APP-GOV-07",
        requested_amount_usd=70000.0,
        rating_category="C",
        ltv_status="HEALTHY",
        exceeds_usury_cap=False,
    )
    # Quórum 3, Mayoría 2
    vote1 = CommitteeVote(
        voter_id="USR-01",
        voter_name="Carlos Riesgos",
        role=CommitteeMemberRole.RISK_OFFICER,
        vote=CommitteeVoteType.REJECT,
        notes="Riesgo de sobreendeudamiento elevado.",
        voted_at="2026-10-30T10:00:00Z",
    )
    res1 = GovernanceEngine.tally_resolution(req, [], vote1)

    vote2 = CommitteeVote(
        voter_id="USR-02",
        voter_name="Laura Gerente",
        role=CommitteeMemberRole.CREDIT_MANAGER,
        vote=CommitteeVoteType.REJECT,
        notes="Flujo de caja insuficiente para el servicio de deuda proyectado.",
        voted_at="2026-10-30T10:02:00Z",
    )
    res2 = GovernanceEngine.tally_resolution(req, res1.votes, vote2)

    assert res2.status == ResolutionStatus.REJECTED_BY_COMMITTEE
    assert res2.is_final is True
    assert res2.act_number is not None
    assert "RECHAZADO POR COMITÉ" in res2.resolution_notes


def test_05_covenants_and_conditional_approval() -> None:
    """TEST-05: Inclusión de covenants resolutivos y aprobación condicional (APPROVED_WITH_CONDITIONS)."""
    req = GovernanceEngine.evaluate_required_level(
        application_id="APP-GOV-08",
        requested_amount_usd=55000.0,
        rating_category="B",
        ltv_status="WARNING",
        exceeds_usury_cap=False,
    )
    # Quórum 3, Mayoría 2
    cov1 = CreditCovenant(
        code="COV-INS-01",
        description="Constituir póliza de todo riesgo endosada a favor de la cooperativa.",
        covenant_type="GARANTIA",
        due_days=15,
    )
    vote1 = CommitteeVote(
        voter_id="USR-01",
        voter_name="Carlos Riesgos",
        role=CommitteeMemberRole.RISK_OFFICER,
        vote=CommitteeVoteType.CONDITION,
        notes="Aprobado sujeto al endoso previo de póliza.",
        covenants=[cov1],
        voted_at="2026-10-30T10:00:00Z",
    )
    res1 = GovernanceEngine.tally_resolution(req, [], vote1)
    assert len(res1.approved_covenants) == 1
    assert res1.approved_covenants[0].code == "COV-INS-01"

    cov2 = CreditCovenant(
        code="COV-FIN-02",
        description="Presentar estados financieros intermedios al cierre de cada semestre.",
        covenant_type="FINANCIERO",
        due_days=180,
    )
    vote2 = CommitteeVote(
        voter_id="USR-02",
        voter_name="Laura Gerente",
        role=CommitteeMemberRole.CREDIT_MANAGER,
        vote=CommitteeVoteType.APPROVE,
        notes="Concurro con la condición impuesta.",
        covenants=[cov2],
        voted_at="2026-10-30T10:02:00Z",
    )
    res2 = GovernanceEngine.tally_resolution(req, res1.votes, vote2)

    # 1 Aprobación + 1 Condición = 2 votos favorables (alcanza mayoría de 2), con condición -> APPROVED_WITH_CONDITIONS
    assert res2.status == ResolutionStatus.APPROVED_WITH_CONDITIONS
    assert res2.is_final is True
    assert len(res2.approved_covenants) == 2
    assert res2.act_number is not None


@pytest.mark.asyncio
async def test_06_http_rest_committee_endpoints_and_persistence() -> None:
    """TEST-06: Endpoints HTTP REST GET/POST /committee, persistencia y RFC 7807 ante 404/400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Crear solicitud crediticia para evaluación de comité
        init_payload = {
            "associated_id": "ASOC-SPEC13-01",
            "business_name": "Agropecuaria El Porvenir SAS",
            "sector": "Agropecuario",
            "requested_amount_usd": 65000.0,
            "term_months": 36,
            "financial_data": {
                "operating_cash_flow": 85000.0,
                "annual_debt_service": 25000.0,
                "current_assets": 110000.0,
                "current_liabilities": 45000.0,
                "cash_balance": 35000.0,
                "monthly_burn_rate": 5000.0,
                "negative_balance_days": 0,
                "top_client_revenue_percentage": 25.0,
            },
        }
        res_init = await client.post("/api/v1/underwritings", json=init_payload)
        assert res_init.status_code == 201
        app_id = res_init.json()["application_id"]

        # 2. Consultar estado inicial del comité vía GET /committee
        res_get_init = await client.get(f"/api/v1/underwritings/{app_id}/committee")
        assert res_get_init.status_code == 200
        init_committee = res_get_init.json()
        assert init_committee["application_id"] == app_id
        assert init_committee["governance_level"] == "LEVEL_3_COMMITTEE"
        assert init_committee["status"] == "IN_DELIBERATION"
        assert len(init_committee["votes"]) == 0

        # 3. Emitir primer voto colegiado (Oficial de Riesgo: CONDITION)
        vote_payload_1 = {
            "voter_id": "USR-OFICIAL-01",
            "voter_name": "Carlos Riesgos",
            "role": "RISK_OFFICER",
            "vote": "CONDITION",
            "notes": "Aprobado condicionado a presentar garantía hipotecaria inscrita.",
            "covenants": [
                {
                    "code": "COV-HIP-01",
                    "description": "Certificado de tradición y libertad con hipoteca inscrita de primer grado.",
                    "covenant_type": "GARANTIA",
                    "due_days": 20,
                }
            ],
        }
        res_vote_1 = await client.post(
            f"/api/v1/underwritings/{app_id}/committee/votes", json=vote_payload_1
        )
        assert res_vote_1.status_code == 200
        data_vote_1 = res_vote_1.json()
        assert len(data_vote_1["votes"]) == 1
        assert data_vote_1["is_final"] is False
        assert len(data_vote_1["approved_covenants"]) == 1

        # 4. Emitir segundo voto colegiado para alcanzar mayoría (Gerente: APPROVE)
        vote_payload_2 = {
            "voter_id": "USR-GERENTE-02",
            "voter_name": "Laura Gómez",
            "role": "CREDIT_MANAGER",
            "vote": "APPROVE",
            "notes": "Concurro con la aprobación técnica y las condiciones acordadas.",
            "covenants": [],
        }
        res_vote_2 = await client.post(
            f"/api/v1/underwritings/{app_id}/committee/votes", json=vote_payload_2
        )
        assert res_vote_2.status_code == 200
        data_vote_2 = res_vote_2.json()
        assert len(data_vote_2["votes"]) == 2
        assert data_vote_2["is_final"] is True
        assert data_vote_2["status"] == "APPROVED_WITH_CONDITIONS"
        assert data_vote_2["act_number"] is not None
        assert data_vote_2["act_number"].startswith("ACTA-")

        # 5. Consultar expediente general y verificar committee_resolution incrustado
        res_full = await client.get(f"/api/v1/underwritings/{app_id}")
        assert res_full.status_code == 200
        full_doc = res_full.json()
        assert full_doc["committee_resolution"] is not None
        assert full_doc["committee_resolution"]["act_number"] == data_vote_2["act_number"]
        assert full_doc["human_approved"] is True
        assert full_doc["is_completed"] is True

        # 6. Intento de votar en una resolución ya finalizada debe retornar 400 Bad Request (RFC 7807)
        res_vote_late = await client.post(
            f"/api/v1/underwritings/{app_id}/committee/votes",
            json={
                "voter_id": "USR-DIRECTOR-03",
                "voter_name": "Pedro Director",
                "role": "OPERATIONS_DIRECTOR",
                "vote": "APPROVE",
                "notes": "Voto tardío",
                "covenants": [],
            },
        )
        assert res_vote_late.status_code == 400
        prob_late = res_vote_late.json()
        assert prob_late["status"] == 400
        assert "ya ha sido emitida" in prob_late["detail"]

        # 7. ID inexistente debe retornar 404 Problem Details (RFC 7807)
        res_404 = await client.get("/api/v1/underwritings/non-existent-app-id/committee")
        assert res_404.status_code == 404
        prob_404 = res_404.json()
        assert prob_404["status"] == 404
        assert "title" in prob_404
