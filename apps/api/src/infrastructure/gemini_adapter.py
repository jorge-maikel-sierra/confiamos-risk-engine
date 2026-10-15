"""Adaptador de infraestructura para inferencia de riesgo con Google Gemini (SPEC-01).

Implementa la separación de capas: protocolo desacoplado + cliente real + mock para testing.
"""

from typing import Protocol

from src.domain.metrics import FinancialHealthMetrics
from src.domain.state import CreditRecommendation, UnderwritingVerdict


class RiskAuditorProtocol(Protocol):
    """Protocolo abstracto para el servicio de auditoría de riesgo."""

    async def audit_application(
        self,
        business_name: str,
        requested_amount_usd: float,
        term_months: int,
        metrics: FinancialHealthMetrics,
    ) -> UnderwritingVerdict:
        """Emite el dictamen estructurado de riesgo para una solicitud."""
        ...


class MockGeminiAuditor:
    """Implementación mock determinística para tests unitarios y CI/CD."""

    def __init__(self, forced_verdict: UnderwritingVerdict | None = None) -> None:
        self.forced_verdict = forced_verdict
        self.call_count = 0

    async def audit_application(
        self,
        business_name: str,
        requested_amount_usd: float,
        term_months: int,
        metrics: FinancialHealthMetrics,
    ) -> UnderwritingVerdict:
        self.call_count += 1
        if self.forced_verdict:
            return self.forced_verdict

        # Lógica heurística mock acorde a las métricas para pruebas realistas
        is_solvent = metrics.dscr_result.is_solvent
        has_critical_flags = any(
            flag in metrics.anomaly_flags
            for flag in ["FLAG_NEGATIVE_OPERATING_CASH_FLOW", "FLAG_OVERDRAFT_DETECTED"]
        )

        if is_solvent and not has_critical_flags:
            recommendation = CreditRecommendation.APROBADO
            confidence = 0.92
            summary = (
                f"La empresa {business_name} presenta adecuada cobertura de deuda "
                f"(DSCR: {metrics.dscr_result.dscr:.2f}) y liquidez suficiente para "
                f"el préstamo solicitado de ${requested_amount_usd:,.2f}."
            )
            risks: list[str] = []
            questions: list[str] = [
                "¿Se mantendrán los contratos clave durante el próximo ejercicio?"
            ]
        elif is_solvent and has_critical_flags:
            recommendation = CreditRecommendation.APROBADO_CONDICIONADO
            confidence = 0.78
            summary = (
                f"La empresa {business_name} cumple con el ratio de cobertura pero presenta "
                "alertas operativas que requieren garantías adicionales."
            )
            risks = metrics.anomaly_flags.copy()
            questions = [
                "Explicar los días con saldo negativo registrados en los extractos.",
                "Presentar aval o garantía líquida equivalente al 20% del crédito.",
            ]
        else:
            recommendation = CreditRecommendation.RECHAZADO
            confidence = 0.95
            summary = (
                f"La empresa {business_name} no genera flujo de caja suficiente para cubrir "
                "el servicio de deuda. Solicitud no viable bajo políticas de Cooperativa Confiamos."
            )
            risks = ["DSCR deficitario"] + metrics.anomaly_flags
            questions = ["¿Existen planes de reestructuración de pasivos existentes?"]

        return UnderwritingVerdict(
            recommendation=recommendation,
            confidence_score=confidence,
            executive_summary=summary,
            key_strengths=["Actividad comercial comprobada"],
            identified_risks=risks,
            due_diligence_questions=questions,
        )


class GeminiRiskAuditor:
    """Implementación de producción que invoca la API oficial de Google Gemini."""

    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash") -> None:
        self.api_key = api_key
        self.model_name = model_name
        # Inicialización diferida del cliente oficial
        from google import genai

        self.client = genai.Client(api_key=api_key)

    async def audit_application(
        self,
        business_name: str,
        requested_amount_usd: float,
        term_months: int,
        metrics: FinancialHealthMetrics,
    ) -> UnderwritingVerdict:
        from google.genai import types

        flags_str = ", ".join(metrics.anomaly_flags) if metrics.anomaly_flags else "Ninguna"
        dscr_val = metrics.dscr_result.dscr
        is_free = metrics.dscr_result.is_debt_free

        prompt = f"""
Eres el Oficial Senior de Riesgo de la Cooperativa Confiamos.
Analiza la siguiente solicitud de crédito comercial evaluando los indicadores determinísticos:

EMPRESA: {business_name}
MONTO SOLICITADO: ${requested_amount_usd:,.2f} USD
PLAZO: {term_months} meses

INDICADORES DETERMINÍSTICOS CALCULADOS (MATEMÁTICA PURA):
- DSCR: {dscr_val} (Libre de deuda: {is_free})
- Ratio de Liquidez Corriente: {metrics.current_ratio}
- Runway estimado: {metrics.runway_months} meses
- Banderas de anomalías detectadas: {flags_str}

REGLAS DE DECISIÓN:
1. Si el DSCR es menor a 1.25, no aprobar de forma directa.
2. Si hay flujo operativo negativo o sobregiros, emitir APROBADO_CONDICIONADO o RECHAZADO.
3. Genera preguntas de Due Diligence concretas y específicas para el solicitante.
"""

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=UnderwritingVerdict,
                temperature=0.1,  # Temperatura baja para consistencia y rigor bancario
            ),
        )

        return UnderwritingVerdict.model_validate_json(response.text)
