"""Dominio para búsqueda semántica de riesgo histórico con pgvector (SPEC-05).

Define contratos de interfaz, entidades y generador sintético de perfiles crediticios.
"""

import math
import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Protocol


class LoanOutcome(StrEnum):
    """Desenlace histórico de la operación crediticia."""

    CARTERA_SANA = "CARTERA_SANA"
    DEFAULT_MORA = "DEFAULT_MORA"
    REESTRUCTURADO = "REESTRUCTURADO"


@dataclass
class HistoricalLoanPrecedent:
    """Precedente histórico de crédito recuperado por similitud vectorial."""

    loan_id: str
    business_name: str
    sector: str
    requested_amount_usd: float
    dscr: float
    current_ratio: float
    anomaly_flags: list[str]
    outcome: LoanOutcome
    outcome_summary: str
    similarity_score: float

    def to_dict(self) -> dict[str, Any]:
        """Serializa el precedente a diccionario primitivo."""
        data = asdict(self)
        data["outcome"] = self.outcome.value
        return data


def build_credit_profile_text(
    business_name: str,
    sector: str,
    requested_amount_usd: float,
    term_months: int,
    dscr: float,
    current_ratio: float,
    runway_months: float,
    anomaly_flags: list[str],
) -> str:
    """Sintetiza el perfil crediticio en texto estructurado denso para embedding."""
    flags_desc = ", ".join(anomaly_flags) if anomaly_flags else "Sin anomalías"
    return (
        f"Sector: {sector}. Empresa: {business_name}. "
        f"Monto: ${requested_amount_usd:,.2f} USD a {term_months} meses. "
        f"DSCR: {dscr:.2f}, Cobertura Corriente: {current_ratio:.2f}, "
        f"Runway: {runway_months:.1f} meses. "
        f"Alertas de Riesgo: {flags_desc}."
    )


def compute_cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Calcula la similitud coseno matemática entre dos vectores normalizados."""
    if len(vec_a) != len(vec_b) or not vec_a:
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    similarity = dot_product / (norm_a * norm_b)
    # Clamp en rango [-1.0, 1.0] por precisión numérica
    return max(-1.0, min(1.0, similarity))


class IEmbeddingGenerator(Protocol):
    """Protocolo desacoplado para generación de embeddings densos."""

    async def generate_embedding(self, text: str) -> list[float]:
        """Retorna un vector denso de 768 dimensiones para el texto dado."""
        ...


class IVectorSearchRepository(Protocol):
    """Protocolo desacoplado para búsqueda de precedentes por similitud vectorial."""

    async def search_similar_loans(
        self,
        embedding: list[float],
        limit: int = 3,
    ) -> list[HistoricalLoanPrecedent]:
        """Retorna los k créditos históricos más análogos ordenados por similitud."""
        ...

    async def seed_dataset_if_empty(self) -> None:
        """Siembra los 20 casos históricos en la base de datos si está vacía."""
        ...


class MockEmbeddingGenerator:
    """Generador determinístico de embeddings de 768 dimensiones para testing offline."""

    def __init__(self, dimension: int = 768) -> None:
        self.dimension = dimension

    async def generate_embedding(self, text: str) -> list[float]:
        """Genera un vector unitario determinístico basado en los tokens del texto."""
        words = re.findall(r"\w+", text.lower())
        vec = [0.0] * self.dimension

        if not words:
            vec[0] = 1.0
            return vec

        for idx, word in enumerate(words):
            val = sum(ord(c) for c in word)
            pos = (val * 31 + idx * 17) % self.dimension
            vec[pos] += 1.0 + (val % 10) * 0.1

        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0.0:
            vec = [v / norm for v in vec]
        else:
            vec[0] = 1.0

        return vec


# Dataset semilla con 20 casos históricos de crédito PyME de Cooperativa Confiamos
SEED_HISTORICAL_LOANS: list[dict[str, Any]] = [
    {
        "loan_id": "HIST-001",
        "associated_id": "CONF-HIST-101",
        "business_name": "Agroindustrias del Norte S.A.",
        "sector": "Agroindustria",
        "requested_amount_usd": 45000.0,
        "term_months": 36,
        "dscr": 1.15,
        "current_ratio": 1.10,
        "anomaly_flags": ["FLAG_SEASONAL_VARIATION"],
        "outcome": LoanOutcome.CARTERA_SANA,
        "outcome_summary": (
            "Superó bache estacional de flujo mediante pignoración de cosecha. "
            "Pagos al día con récord intachable."
        ),
    },
    {
        "loan_id": "HIST-002",
        "associated_id": "CONF-HIST-102",
        "business_name": "Distribuidora Mayorista Los Andes",
        "sector": "Comercio",
        "requested_amount_usd": 65000.0,
        "term_months": 24,
        "dscr": 1.08,
        "current_ratio": 0.95,
        "anomaly_flags": ["FLAG_OVERDRAFT_DETECTED", "FLAG_CLIENT_CONCENTRATION_HIGH"],
        "outcome": LoanOutcome.DEFAULT_MORA,
        "outcome_summary": (
            "Cesación de pagos al mes 8. Pérdida del cliente principal combinada con uso "
            "reiterado de líneas de sobregiro."
        ),
    },
    {
        "loan_id": "HIST-003",
        "associated_id": "CONF-HIST-103",
        "business_name": "Manufacturas Textiles Andinas Ltda.",
        "sector": "Manufactura",
        "requested_amount_usd": 80000.0,
        "term_months": 48,
        "dscr": 1.45,
        "current_ratio": 1.65,
        "anomaly_flags": [],
        "outcome": LoanOutcome.CARTERA_SANA,
        "outcome_summary": (
            "Excelente desempeño operativo. Amortización anticipada total a los 36 meses."
        ),
    },
    {
        "loan_id": "HIST-004",
        "associated_id": "CONF-HIST-104",
        "business_name": "Transportes & Carga del Litoral",
        "sector": "Transporte y Logística",
        "requested_amount_usd": 55000.0,
        "term_months": 36,
        "dscr": 1.20,
        "current_ratio": 1.15,
        "anomaly_flags": ["FLAG_NEGATIVE_OPERATING_CASH_FLOW"],
        "outcome": LoanOutcome.REESTRUCTURADO,
        "outcome_summary": (
            "Reestructurado a 48 meses con periodo de gracia de 6 meses por incremento "
            "súbito de combustibles."
        ),
    },
    {
        "loan_id": "HIST-005",
        "associated_id": "CONF-HIST-105",
        "business_name": "Cadena Gastronómica El Fogón Criollo",
        "sector": "Gastronomía",
        "requested_amount_usd": 30000.0,
        "term_months": 18,
        "dscr": 1.85,
        "current_ratio": 1.90,
        "anomaly_flags": [],
        "outcome": LoanOutcome.CARTERA_SANA,
        "outcome_summary": (
            "Flujo de caja diario sólido. Pago puntual de todas las cuotas pactadas."
        ),
    },
    {
        "loan_id": "HIST-006",
        "associated_id": "CONF-HIST-106",
        "business_name": "Constructora Urbana del Valle",
        "sector": "Construcción",
        "requested_amount_usd": 120000.0,
        "term_months": 36,
        "dscr": 0.95,
        "current_ratio": 0.88,
        "anomaly_flags": ["FLAG_DEFICIT_DSCR", "FLAG_OVERDRAFT_DETECTED"],
        "outcome": LoanOutcome.DEFAULT_MORA,
        "outcome_summary": (
            "Default total al mes 5 por sobrecostos de obra e iliquidez estructural sin garantías."
        ),
    },
    {
        "loan_id": "HIST-007",
        "associated_id": "CONF-HIST-107",
        "business_name": "Clínica Veterinaria & Farmacia San Roque",
        "sector": "Salud y Servicios",
        "requested_amount_usd": 25000.0,
        "term_months": 24,
        "dscr": 1.55,
        "current_ratio": 1.40,
        "anomaly_flags": [],
        "outcome": LoanOutcome.CARTERA_SANA,
        "outcome_summary": (
            "Alta rotación de inventarios y demanda inelástica. Crédito cancelado con éxito."
        ),
    },
    {
        "loan_id": "HIST-008",
        "associated_id": "CONF-HIST-108",
        "business_name": "Metalmecánica Integral de Occidente",
        "sector": "Metalmecánica",
        "requested_amount_usd": 70000.0,
        "term_months": 48,
        "dscr": 1.30,
        "current_ratio": 1.35,
        "anomaly_flags": ["FLAG_CLIENT_CONCENTRATION_HIGH"],
        "outcome": LoanOutcome.CARTERA_SANA,
        "outcome_summary": (
            "Mitigó concentración de clientes mediante diversificación de contratos preventivos."
        ),
    },
    {
        "loan_id": "HIST-009",
        "associated_id": "CONF-HIST-109",
        "business_name": "Tecnología y Redes del Pacífico",
        "sector": "Tecnología",
        "requested_amount_usd": 40000.0,
        "term_months": 24,
        "dscr": 1.60,
        "current_ratio": 2.10,
        "anomaly_flags": [],
        "outcome": LoanOutcome.CARTERA_SANA,
        "outcome_summary": (
            "Contratos SaaS recurrentes en dólares. Amortización perfecta sin retrasos."
        ),
    },
    {
        "loan_id": "HIST-010",
        "associated_id": "CONF-HIST-110",
        "business_name": "Calzados y Marroquinería Imperial",
        "sector": "Manufactura",
        "requested_amount_usd": 35000.0,
        "term_months": 24,
        "dscr": 1.02,
        "current_ratio": 0.98,
        "anomaly_flags": ["FLAG_NEGATIVE_OPERATING_CASH_FLOW"],
        "outcome": LoanOutcome.DEFAULT_MORA,
        "outcome_summary": (
            "Mora mayor a 120 días por caída de ventas y acumulación de producto terminado."
        ),
    },
    {
        "loan_id": "HIST-011",
        "associated_id": "CONF-HIST-111",
        "business_name": "Panificadora y Alimentos Dulce Trigo",
        "sector": "Alimentos",
        "requested_amount_usd": 28000.0,
        "term_months": 20,
        "dscr": 1.40,
        "current_ratio": 1.30,
        "anomaly_flags": [],
        "outcome": LoanOutcome.CARTERA_SANA,
        "outcome_summary": (
            "Comercio minorista de alto volumen. Cumplimiento estricto del plan de pagos."
        ),
    },
    {
        "loan_id": "HIST-012",
        "associated_id": "CONF-HIST-112",
        "business_name": "Insumos Químicos y Agropecuarios del Sur",
        "sector": "Comercio",
        "requested_amount_usd": 90000.0,
        "term_months": 36,
        "dscr": 1.22,
        "current_ratio": 1.25,
        "anomaly_flags": ["FLAG_SEASONAL_VARIATION"],
        "outcome": LoanOutcome.REESTRUCTURADO,
        "outcome_summary": (
            "Ajuste de cronograma para coincidir con ciclos trimestrales agrícolas. Al día."
        ),
    },
    {
        "loan_id": "HIST-013",
        "associated_id": "CONF-HIST-113",
        "business_name": "Eco-Plásticos y Reciclaje Circular",
        "sector": "Reciclaje y Ambiente",
        "requested_amount_usd": 50000.0,
        "term_months": 36,
        "dscr": 1.38,
        "current_ratio": 1.45,
        "anomaly_flags": [],
        "outcome": LoanOutcome.CARTERA_SANA,
        "outcome_summary": (
            "Operación escalable con demanda creciente de material reciclado. Cancelado."
        ),
    },
    {
        "loan_id": "HIST-014",
        "associated_id": "CONF-HIST-114",
        "business_name": "Logística Frigorífica Express",
        "sector": "Transporte y Logística",
        "requested_amount_usd": 85000.0,
        "term_months": 48,
        "dscr": 1.12,
        "current_ratio": 1.05,
        "anomaly_flags": ["FLAG_OVERDRAFT_DETECTED"],
        "outcome": LoanOutcome.DEFAULT_MORA,
        "outcome_summary": (
            "Deterioro acelerado de flota de camiones y contingencia laboral. Cartera castigada."
        ),
    },
    {
        "loan_id": "HIST-015",
        "associated_id": "CONF-HIST-115",
        "business_name": "Papelería & Editorial Moderna",
        "sector": "Comercio",
        "requested_amount_usd": 22000.0,
        "term_months": 18,
        "dscr": 1.70,
        "current_ratio": 1.80,
        "anomaly_flags": [],
        "outcome": LoanOutcome.CARTERA_SANA,
        "outcome_summary": (
            "Temporada escolar exitosa con ingresos suficientes para prepago del saldo a capital."
        ),
    },
    {
        "loan_id": "HIST-016",
        "associated_id": "CONF-HIST-116",
        "business_name": "Distribuidora de Repuestos Automotrices Diesel",
        "sector": "Automotriz",
        "requested_amount_usd": 60000.0,
        "term_months": 30,
        "dscr": 1.28,
        "current_ratio": 1.50,
        "anomaly_flags": [],
        "outcome": LoanOutcome.CARTERA_SANA,
        "outcome_summary": "Márgenes brutos estables y cobranza estricta a talleres afiliados.",
    },
    {
        "loan_id": "HIST-017",
        "associated_id": "CONF-HIST-117",
        "business_name": "Servicios Hoteleros Sol y Luna",
        "sector": "Hotelería y Turismo",
        "requested_amount_usd": 75000.0,
        "term_months": 36,
        "dscr": 1.18,
        "current_ratio": 1.12,
        "anomaly_flags": ["FLAG_SEASONAL_VARIATION"],
        "outcome": LoanOutcome.REESTRUCTURADO,
        "outcome_summary": (
            "Cuotas escalonadas según temporada turística permitieron normalizar la cartera."
        ),
    },
    {
        "loan_id": "HIST-018",
        "associated_id": "CONF-HIST-118",
        "business_name": "Agropecuaria Ganadera San Jerónimo",
        "sector": "Agroindustria",
        "requested_amount_usd": 95000.0,
        "term_months": 48,
        "dscr": 1.50,
        "current_ratio": 1.60,
        "anomaly_flags": [],
        "outcome": LoanOutcome.CARTERA_SANA,
        "outcome_summary": "Ventas spot de ganado de ceba y subastas con excelente liquidez.",
    },
    {
        "loan_id": "HIST-019",
        "associated_id": "CONF-HIST-119",
        "business_name": "Ferretería Industrial El Tornillo de Oro",
        "sector": "Comercio",
        "requested_amount_usd": 40000.0,
        "term_months": 24,
        "dscr": 1.05,
        "current_ratio": 0.90,
        "anomaly_flags": ["FLAG_OVERDRAFT_DETECTED", "FLAG_DEFICIT_DSCR"],
        "outcome": LoanOutcome.DEFAULT_MORA,
        "outcome_summary": (
            "Descapitalización por retiro de socios. Insolvencia judicial y ejecución de pagarés."
        ),
    },
    {
        "loan_id": "HIST-020",
        "associated_id": "CONF-HIST-120",
        "business_name": "Laboratorio Odontológico Dental Precision",
        "sector": "Salud y Servicios",
        "requested_amount_usd": 32000.0,
        "term_months": 24,
        "dscr": 1.65,
        "current_ratio": 1.75,
        "anomaly_flags": [],
        "outcome": LoanOutcome.CARTERA_SANA,
        "outcome_summary": (
            "Clientes profesionales con pago a 30 días. Préstamo amortizado sin demoras."
        ),
    },
]


class MockVectorSearchRepository:
    """Repositorio en memoria con cálculo matemático exacto de similitud coseno."""

    def __init__(
        self,
        embedder: IEmbeddingGenerator | None = None,
        seed_data: list[dict[str, Any]] | None = None,
    ) -> None:
        self.embedder = embedder or MockEmbeddingGenerator()
        self.seed_data = seed_data or SEED_HISTORICAL_LOANS
        self._items: list[dict[str, Any]] = []
        self._seeded: bool = False

    async def seed_dataset_if_empty(self) -> None:
        """Inicializa los vectores de los 20 casos semilla en memoria."""
        if self._seeded and self._items:
            return

        self._items = []
        for raw in self.seed_data:
            text = build_credit_profile_text(
                business_name=raw["business_name"],
                sector=raw["sector"],
                requested_amount_usd=raw["requested_amount_usd"],
                term_months=raw["term_months"],
                dscr=raw["dscr"],
                current_ratio=raw["current_ratio"],
                runway_months=12.0,
                anomaly_flags=raw.get("anomaly_flags", []),
            )
            emb = await self.embedder.generate_embedding(text)
            item_copy = raw.copy()
            item_copy["embedding"] = emb
            self._items.append(item_copy)

        self._seeded = True

    async def search_similar_loans(
        self,
        embedding: list[float],
        limit: int = 3,
    ) -> list[HistoricalLoanPrecedent]:
        """Busca los k créditos más cercanos usando similitud coseno pura."""
        if not self._seeded:
            await self.seed_dataset_if_empty()

        scored_items: list[tuple[float, dict[str, Any]]] = []
        for item in self._items:
            sim = compute_cosine_similarity(embedding, item["embedding"])
            scored_items.append((sim, item))

        # Orden descendente por similitud coseno
        scored_items.sort(key=lambda x: x[0], reverse=True)
        top_k = scored_items[:limit]

        results: list[HistoricalLoanPrecedent] = []
        for score, raw in top_k:
            precedent = HistoricalLoanPrecedent(
                loan_id=raw["loan_id"],
                business_name=raw["business_name"],
                sector=raw["sector"],
                requested_amount_usd=raw["requested_amount_usd"],
                dscr=raw["dscr"],
                current_ratio=raw["current_ratio"],
                anomaly_flags=raw.get("anomaly_flags", []),
                outcome=raw["outcome"],
                outcome_summary=raw["outcome_summary"],
                similarity_score=round(score, 4),
            )
            results.append(precedent)

        return results
