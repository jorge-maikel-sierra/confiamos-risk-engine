"""Motor de Gobernanza, Matriz de Atribuciones y Comité de Crédito Colegiado (SPEC-13).

Implementa la lógica determinística de arquitectura hexagonal pura para:
1. Evaluar el nivel de atribución requerido (Oficial, Gerencia, Comité Colegiado, Consejo).
2. Computar votos independientes multi-rol con quórum y mayorías reglamentarias.
3. Consolidar covenants contractuales y generar el Acta Resolutiva Oficial.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ApprovalAuthorityLevel(StrEnum):
    """Niveles de competencia legal y atribución estatutaria para aprobación de créditos."""

    LEVEL_1_OFFICER = "LEVEL_1_OFFICER"  # Oficial individual (Monto <= $15k, Rating A/B, LTV <= 70%)
    LEVEL_2_MANAGER = "LEVEL_2_MANAGER"  # Gerente de Riesgo / Agencia (Monto <= $40k o LTV Warning)
    LEVEL_3_COMMITTEE = "LEVEL_3_COMMITTEE"  # Comité Colegiado (Monto <= $100k o Rating C)
    LEVEL_4_BOARD = "LEVEL_4_BOARD"  # Consejo de Administración (Monto > $100k, Rating D/E o Alerta Usura)


class CommitteeVoteType(StrEnum):
    """Sentido del voto emitido por un miembro de comité."""

    APPROVE = "APPROVE"  # Aprobado sin observaciones adicionales
    CONDITION = "CONDITION"  # Aprobado sujeto al cumplimiento de covenants específicos
    REJECT = "REJECT"  # Rechazado por riesgo inaceptable o falta de viabilidad


class CommitteeMemberRole(StrEnum):
    """Roles con facultades de voto en el gobierno crediticio."""

    RISK_OFFICER = "RISK_OFFICER"  # Oficial / Analista Senior de Riesgos
    CREDIT_MANAGER = "CREDIT_MANAGER"  # Gerente de Crédito y Cartera
    OPERATIONS_DIRECTOR = "OPERATIONS_DIRECTOR"  # Director de Operaciones / Finanzas
    BOARD_DIRECTOR = "BOARD_DIRECTOR"  # Vocal / Delegado del Consejo de Administración


class ResolutionStatus(StrEnum):
    """Estado resolutivo de la sesión de comité."""

    IN_DELIBERATION = "IN_DELIBERATION"  # Sesión abierta en espera de quórum o votos
    APPROVED_BY_COMMITTEE = "APPROVED_BY_COMMITTEE"  # Aprobado por mayoría reglamentaria
    APPROVED_WITH_CONDITIONS = "APPROVED_WITH_CONDITIONS"  # Aprobado por mayoría con covenants vinculantes
    REJECTED_BY_COMMITTEE = "REJECTED_BY_COMMITTEE"  # Rechazado por votos mayoritarios negativos


class CreditCovenant(BaseModel):
    """Compromiso o condición vinculante impuesta por el comité para el desembolso."""

    code: str = Field(description="Identificador mnemotécnico del covenant")
    description: str = Field(min_length=5, description="Obligación pactada")
    covenant_type: str = Field(
        default="GARANTIA",
        description="Tipo de condición: GARANTIA, FINANCIERO, DOCUMENTAL",
    )
    due_days: int = Field(default=30, gt=0, description="Días hábiles para subsanación o entrega")


class CommitteeVote(BaseModel):
    """Voto nominal emitido por un integrante del comité."""

    voter_id: str = Field(description="Identificador o usuario del votante")
    voter_name: str = Field(description="Nombre y apellido del votante")
    role: CommitteeMemberRole = Field(description="Rol estatutario ejercido")
    vote: CommitteeVoteType = Field(description="Sentido del voto")
    notes: str = Field(min_length=3, description="Justificación técnica de la decisión")
    covenants: list[CreditCovenant] = Field(
        default_factory=list, description="Covenants aportados por este voto"
    )
    voted_at: str = Field(description="Timestamp ISO-8601 del voto")


class GovernanceRequirement(BaseModel):
    """Requisito normativo de instancia decisoria determinado por el motor."""

    application_id: str
    required_level: ApprovalAuthorityLevel
    required_level_title: str
    required_quorum: int = Field(ge=1, description="Número mínimo de votos para resolución en firme")
    required_roles: list[CommitteeMemberRole]
    regulatory_justification: str


class CommitteeResolution(BaseModel):
    """Acta resolutiva consolidada de comité y deliberación colegiada (SPEC-13)."""

    application_id: str
    act_number: str = Field(description="Folio oficial consecutivo del acta (ACTA-2026-XXXX)")
    governance_level: ApprovalAuthorityLevel
    governance_title: str = Field(default="", description="Denominación formal del nivel de atribución")
    status: ResolutionStatus
    required_quorum: int
    required_roles: list[CommitteeMemberRole] = Field(
        default_factory=list, description="Roles estatutarios requeridos para la sesión"
    )
    votes_cast_count: int
    is_quorum_reached: bool
    votes: list[CommitteeVote] = Field(default_factory=list)
    approved_covenants: list[CreditCovenant] = Field(default_factory=list)
    resolution_notes: str
    resolved_at: str | None = Field(default=None, description="Fecha de resolución final o None si delibera")
    offer_expires_at: str | None = Field(
        default=None, description="Vencimiento de la oferta aprobada (30 días)"
    )
    is_final: bool = Field(description="True si la decisión es firme y cierra el expediente")


class GovernanceEngine:
    """Motor determinístico de cálculo de facultades y resolución colegiada."""

    @classmethod
    def evaluate_required_level(
        cls,
        application_id: str,
        requested_amount_usd: float,
        rating_category: str = "C",
        ltv_status: str = "UNSECURED",
        exceeds_usury_cap: bool = False,
    ) -> GovernanceRequirement:
        """Determina la instancia de decisión estatutaria requerida según riesgo y monto."""
        clean_rating = rating_category.upper().strip()
        clean_ltv = ltv_status.upper().strip()

        # Regla 4: Consejo de Administración (Nivel 4)
        if (
            requested_amount_usd > 100000.0
            or clean_rating in ("D", "E")
            or exceeds_usury_cap
        ):
            return GovernanceRequirement(
                application_id=application_id,
                required_level=ApprovalAuthorityLevel.LEVEL_4_BOARD,
                required_level_title="Consejo de Administración / Junta Directiva",
                required_quorum=3,
                required_roles=[
                    CommitteeMemberRole.BOARD_DIRECTOR,
                    CommitteeMemberRole.RISK_OFFICER,
                    CommitteeMemberRole.CREDIT_MANAGER,
                ],
                regulatory_justification=(
                    "Monto superior a $100,000 USD, calificación de riesgo D/E o alerta de usura "
                    "requiere autorización expresa del Consejo de Administración (Art. 42 Estatutos)."
                ),
            )

        # Regla 3: Comité de Crédito Colegiado (Nivel 3)
        if requested_amount_usd > 40000.0 or clean_rating == "C":
            return GovernanceRequirement(
                application_id=application_id,
                required_level=ApprovalAuthorityLevel.LEVEL_3_COMMITTEE,
                required_level_title="Comité de Crédito Colegiado de Sede Central",
                required_quorum=3,
                required_roles=[
                    CommitteeMemberRole.RISK_OFFICER,
                    CommitteeMemberRole.CREDIT_MANAGER,
                    CommitteeMemberRole.OPERATIONS_DIRECTOR,
                ],
                regulatory_justification=(
                    "Monto entre $40,000 y $100,000 USD o calificación C exige quórum colegiado de "
                    "3 miembros con al menos dos votos favorables (Circular Básica Contable SES)."
                ),
            )

        # Regla 2: Gerencia de Riesgo / Agencia (Nivel 2)
        if requested_amount_usd > 15000.0 or clean_ltv == "WARNING":
            return GovernanceRequirement(
                application_id=application_id,
                required_level=ApprovalAuthorityLevel.LEVEL_2_MANAGER,
                required_level_title="Gerencia de Riesgos y Agencia",
                required_quorum=2,
                required_roles=[
                    CommitteeMemberRole.RISK_OFFICER,
                    CommitteeMemberRole.CREDIT_MANAGER,
                ],
                regulatory_justification=(
                    "Monto mediano ($15k a $40k USD) o colateral con cobertura en advertencia "
                    "requiere visto bueno mancomunado de Oficial de Riesgos y Gerente de Crédito."
                ),
            )

        # Regla 1: Oficial de Crédito Individual (Nivel 1)
        return GovernanceRequirement(
            application_id=application_id,
            required_level=ApprovalAuthorityLevel.LEVEL_1_OFFICER,
            required_level_title="Oficial de Crédito Individual (Régimen Ágil)",
            required_quorum=1,
            required_roles=[CommitteeMemberRole.RISK_OFFICER],
            regulatory_justification=(
                "Monto bajo (hasta $15,000 USD) en asociados solventes (Rating A/B) con LTV saludable "
                "habilitado para aprobación ágil por un Oficial de Crédito certificado."
            ),
        )

    @classmethod
    def tally_resolution(
        cls,
        requirement: GovernanceRequirement,
        current_votes: list[CommitteeVote],
        new_vote: CommitteeVote | None = None,
        act_number: str | None = None,
    ) -> CommitteeResolution:
        """Calcula el quórum, consolida votos y emite el dictamen resolutivo del comité."""
        # Unificar votos evitando duplicación por el mismo miembro (rol o voter_id)
        if new_vote:
            if any(v.voter_id == new_vote.voter_id for v in current_votes):
                raise ValueError(
                    f"El miembro {new_vote.voter_name} ({new_vote.voter_id}) ya ha emitido su voto en esta resolución."
                )

        consolidated_votes = list(current_votes)
        if new_vote:
            consolidated_votes.append(new_vote)
        votes_count = len(consolidated_votes)
        quorum_reached = votes_count >= requirement.required_quorum

        # Conteo de votos
        approve_count = sum(1 for v in consolidated_votes if v.vote == CommitteeVoteType.APPROVE)
        condition_count = sum(1 for v in consolidated_votes if v.vote == CommitteeVoteType.CONDITION)
        reject_count = sum(1 for v in consolidated_votes if v.vote == CommitteeVoteType.REJECT)
        favorable_count = approve_count + condition_count

        # Recopilar todos los covenants aportados
        all_covenants: list[CreditCovenant] = []
        for v in consolidated_votes:
            all_covenants.extend(v.covenants)

        majority_needed = math.ceil((requirement.required_quorum + 1) / 2.0)
        now_str = datetime.now(UTC).isoformat()
        act_id = act_number or f"ACTA-{datetime.now(UTC).year}-{uuid.uuid4().hex[:6].upper()}"

        can_resolve_favorable = favorable_count >= majority_needed
        can_resolve_reject = reject_count >= majority_needed
        quorum_reached = votes_count >= requirement.required_quorum or can_resolve_favorable or can_resolve_reject

        if can_resolve_favorable:
            if condition_count > 0:
                status = ResolutionStatus.APPROVED_WITH_CONDITIONS
                notes = (
                    f"APROBADO CON CONDICIONES: Resolución colegiada adoptada con {favorable_count} "
                    f"votos favorables ({approve_count} directos, {condition_count} condicionados) "
                    f"y {reject_count} en contra. Se estipulan {len(all_covenants)} covenants obligatorios."
                )
            else:
                status = ResolutionStatus.APPROVED_BY_COMMITTEE
                notes = (
                    f"APROBADO POR UNANIMIDAD/MAYORÍA: Resolución favorable adoptada con "
                    f"{favorable_count} votos a favor y {reject_count} en contra."
                )
            resolved_at = now_str
            # Oferta válida por 30 días
            expires_at = datetime.fromtimestamp(
                datetime.now(UTC).timestamp() + (30 * 86400), tz=UTC
            ).isoformat()
            is_final = True

        elif can_resolve_reject:
            status = ResolutionStatus.REJECTED_BY_COMMITTEE
            notes = (
                f"RECHAZADO POR COMITÉ: La solicitud fue denegada por mayoría negativa con "
                f"{reject_count} votos de rechazo frente a {favorable_count} votos favorables."
            )
            resolved_at = now_str
            expires_at = None
            is_final = True

        else:
            # Aún no se ha alcanzado la mayoría determinante y faltan votos
            status = ResolutionStatus.IN_DELIBERATION
            notes = (
                f"Sesión abierta: Se han emitido {votes_count} de los {requirement.required_quorum} "
                f"votos requeridos para la instancia {requirement.required_level_title}."
            )
            resolved_at = None
            expires_at = None
            is_final = False

        return CommitteeResolution(
            application_id=requirement.application_id,
            act_number=act_id,
            governance_level=requirement.required_level,
            governance_title=requirement.required_level_title,
            status=status,
            required_quorum=requirement.required_quorum,
            required_roles=requirement.required_roles,
            votes_cast_count=votes_count,
            is_quorum_reached=quorum_reached,
            votes=consolidated_votes,
            approved_covenants=all_covenants,
            resolution_notes=notes,
            resolved_at=resolved_at,
            offer_expires_at=expires_at,
            is_final=is_final,
        )
