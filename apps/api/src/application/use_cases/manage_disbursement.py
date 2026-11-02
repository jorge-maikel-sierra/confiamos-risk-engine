"""Casos de Uso: Compuerta de Desembolso, Verificación de Covenants y Pagaré Digital (SPEC-14).

Orquesta la evaluación de elegibilidad de desembolso, verificación y levantamiento
de condiciones precedentes, liquidación cooperativa y emisión del pagaré digital
con orden de giro bancario.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.application.exceptions import (
    ApplicationConflictError,
    ApplicationNotFoundError,
)
from src.domain.committee import CommitteeResolution
from src.domain.disbursement import (
    CovenantFulfillmentRecord,
    CovenantFulfillmentStatus,
    DisbursementDeductions,
    DisbursementEngine,
    DisbursementGateStatus,
    DisbursementOrder,
    PromissoryNote,
)
from src.domain.repositories import IUnderwritingRepository


class GetDisbursementGateStatusUseCase:
    """Caso de uso para evaluar la compuerta de desembolso y el estado de covenants."""

    def __init__(self, repository: IUnderwritingRepository) -> None:
        self.repository = repository

    async def execute(self, application_id: str) -> DisbursementGateStatus:
        """Determina si el crédito es elegible para giro y calcula la liquidación neta."""
        record = await self.repository.get_by_id(application_id)
        if not record:
            raise ApplicationNotFoundError(application_id)

        raw_order = record.get("disbursement_order") or {}

        # Si ya cuenta con una orden de giro ejecutada formalmente
        if raw_order.get("order_id"):
            order = DisbursementOrder(**raw_order)
            is_eligible, blocking_reasons = DisbursementEngine.evaluate_gate(
                resolution_status="EXECUTED",
                covenants=order.covenants,
                is_already_disbursed=True,
            )
            return DisbursementGateStatus(
                application_id=application_id,
                is_eligible=False,
                resolution_status="EXECUTED",
                pending_covenants_count=0,
                covenants=order.covenants,
                liquidation_preview=order.liquidation,
                disbursement_order=order,
                blocking_reasons=blocking_reasons,
            )

        # Resolución de comité (SPEC-13)
        raw_committee = record.get("committee_resolution")
        if raw_committee:
            committee_res = CommitteeResolution(**raw_committee)
            resolution_status = committee_res.status.value
            approved_covenants = committee_res.approved_covenants
        else:
            resolution_status = "NOT_STARTED"
            approved_covenants = []

        # Covenants de verificación
        if raw_order.get("covenants"):
            covenants = [CovenantFulfillmentRecord(**c) for c in raw_order["covenants"]]
        else:
            covenants = [
                CovenantFulfillmentRecord(
                    code=c.code,
                    description=c.description,
                    covenant_type=c.covenant_type,
                    due_days=c.due_days,
                    status=CovenantFulfillmentStatus.PENDING,
                )
                for c in approved_covenants
            ]

        # Liquidación cooperativa proyectada
        gross_amount = float(record.get("requested_amount_usd", 10000.0))
        raw_pricing = record.get("pricing_proposal") or {}
        monthly_ins_rate = (
            raw_pricing.get("monthly_insurance_rate")
            or raw_pricing.get("insurance_monthly_rate")
        )
        liquidation = DisbursementEngine.calculate_liquidation(
            gross_amount_usd=gross_amount,
            monthly_insurance_rate=monthly_ins_rate,
        )

        is_eligible, blocking_reasons = DisbursementEngine.evaluate_gate(
            resolution_status=resolution_status,
            covenants=covenants,
            is_already_disbursed=False,
        )
        pending_count = sum(1 for c in covenants if c.status == CovenantFulfillmentStatus.PENDING)

        return DisbursementGateStatus(
            application_id=application_id,
            is_eligible=is_eligible,
            resolution_status=resolution_status,
            pending_covenants_count=pending_count,
            covenants=covenants,
            liquidation_preview=liquidation,
            disbursement_order=None,
            blocking_reasons=blocking_reasons,
        )


class VerifyCovenantUseCase:
    """Caso de uso para registrar la verificación o exoneración de un covenant precedente."""

    def __init__(
        self,
        repository: IUnderwritingRepository,
        get_gate_status_use_case: GetDisbursementGateStatusUseCase,
    ) -> None:
        self.repository = repository
        self.get_gate_status_use_case = get_gate_status_use_case

    async def execute(
        self,
        application_id: str,
        code: str,
        verified_by: str,
        notes: str | None = None,
        status: CovenantFulfillmentStatus = CovenantFulfillmentStatus.FULFILLED,
    ) -> DisbursementGateStatus:
        """Actualiza el estado del covenant aportando evidencia auditable."""
        record = await self.repository.get_by_id(application_id)
        if not record:
            raise ApplicationNotFoundError(application_id)

        raw_order = record.get("disbursement_order") or {}
        if raw_order.get("order_id"):
            raise ApplicationConflictError(
                application_id,
                "No se pueden modificar covenants de un crédito que ya ha sido desembolsado.",
            )

        gate_status = await self.get_gate_status_use_case.execute(application_id)
        target_cov: CovenantFulfillmentRecord | None = None
        updated_covenants: list[CovenantFulfillmentRecord] = []

        now_iso = datetime.now(UTC).isoformat()
        for cov in gate_status.covenants:
            if cov.code.upper().strip() == code.upper().strip():
                target_cov = cov.model_copy(
                    update={
                        "status": status,
                        "verified_by": verified_by,
                        "verified_at": now_iso,
                        "evidence_notes": notes or cov.evidence_notes,
                    }
                )
                updated_covenants.append(target_cov)
            else:
                updated_covenants.append(cov)

        if not target_cov:
            raise ApplicationConflictError(
                application_id,
                f"El covenant con código '{code}' no existe en las condiciones del expediente.",
            )

        # Persistir el avance en la orden preliminar
        raw_order["covenants"] = [c.model_dump() for c in updated_covenants]
        await self.repository.save_disbursement_order(
            application_id=application_id,
            disbursement_order=raw_order,
            is_completed=False,
            current_step="PENDING_DISBURSEMENT",
        )

        return await self.get_gate_status_use_case.execute(application_id)


class ExecuteDisbursementUseCase:
    """Caso de uso para generar el pagaré digital, orden de giro y formalizar el desembolso."""

    def __init__(
        self,
        repository: IUnderwritingRepository,
        get_gate_status_use_case: GetDisbursementGateStatusUseCase,
    ) -> None:
        self.repository = repository
        self.get_gate_status_use_case = get_gate_status_use_case

    async def execute(
        self,
        application_id: str,
        destination_bank: str,
        destination_account_number: str,
        account_type: str = "AHORROS",
    ) -> DisbursementOrder:
        """Emite el pagaré y la orden de giro si la compuerta no tiene bloqueos activos."""
        record = await self.repository.get_by_id(application_id)
        if not record:
            raise ApplicationNotFoundError(application_id)

        gate_status = await self.get_gate_status_use_case.execute(application_id)
        if not gate_status.is_eligible:
            reasons = "; ".join(gate_status.blocking_reasons)
            raise ApplicationConflictError(
                application_id,
                f"El desembolso está bloqueado por la compuerta de control: {reasons}",
            )

        debtor_name = str(record.get("business_name", "Asociado Titular"))
        debtor_id = str(record.get("associated_id", "CC-000000"))
        gross_amount = float(record.get("requested_amount_usd", 10000.0))
        term_months = int(record.get("term_months", 12))

        raw_pricing = record.get("pricing_proposal") or {}
        applied_tea = float(
            raw_pricing.get("approved_tea")
            or raw_pricing.get("recommended_tea")
            or 18.5
        )

        promissory_note = DisbursementEngine.create_promissory_note(
            debtor_name=debtor_name,
            debtor_id=debtor_id,
            principal_amount_usd=gross_amount,
            applied_tea=applied_tea,
            term_months=term_months,
        )

        disbursement_order = DisbursementEngine.create_disbursement_order(
            application_id=application_id,
            liquidation=gate_status.liquidation_preview,
            promissory_note=promissory_note,
            destination_bank=destination_bank,
            destination_account_number=destination_account_number,
            account_type=account_type,
            covenants=gate_status.covenants,
        )

        # Persistir orden definitiva y marcar expediente como completado y desembolsado
        await self.repository.save_disbursement_order(
            application_id=application_id,
            disbursement_order=disbursement_order.model_dump(),
            is_completed=True,
            current_step="DISBURSED",
        )

        return disbursement_order
