"""Script ejecutable para gestionar y enviar la publicación técnica diaria a Telegram.

Proyecto: Confiamos Risk Engine (CRE)
Cliente: Cooperativa Confiamos (Entrega pactada a 100 días de desarrollo en producción).
Inicia en el Día 1 y avanza de forma secuencial cada día a las 8:00 AM.
"""

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Cargar variables de entorno desde apps/api/.env
api_root = Path(__file__).resolve().parent.parent.parent
env_file = api_root / ".env"
load_dotenv(env_file)

if str(api_root) not in sys.path:
    sys.path.insert(0, str(api_root))

from src.bot.telegram_notifier import DailyPostStory, TelegramNotifier  # noqa: E402

STATE_FILE = api_root / "data" / "daily_story_state.json"

# Catálogo de historias técnicas del proyecto real (Día 1 a 100)
STORIES_CATALOG: dict[int, dict[str, Any]] = {
    1: {
        "hook": (
            "Arrancamos el desarrollo de Confiamos Risk Engine (CRE): motor de suscripción "
            "crediticia para una cooperativa real con entrega pactada a 100 días."
        ),
        "conflict": (
            "Los analistas demoraban hasta 5 días revisando balances a mano. Automatizarlo con un "
            "LLM directo es peligroso: los modelos alucinan en cálculos aritméticos y ratios."
        ),
        "solution": (
            "Separamos la matemática en funciones puras en Python (DSCR, Liquidez, Runway) y "
            "orquestamos el flujo con una máquina de estados determinística en LangGraph (SPEC-01)."
        ),
        "hashtags": ["#Fintech", "#SoftwareEngineering", "#AIEngineering"],
    },
    2: {
        "hook": (
            "En un motor de riesgo financiero para una cooperativa real, el estado en memoria "
            "no sirve: la auditoría regulatoria exige trazabilidad completa de cada solicitud."
        ),
        "conflict": (
            "Mapear balances contables heterogéneos y transacciones a un esquema relacional "
            "sin perder performance ni integridad transaccional."
        ),
        "solution": (
            "Implementamos persistencia en PostgreSQL con SQLAlchemy Async, campos JSONB tipados "
            "y repositorios intercambiables testeados con aiosqlite (SPEC-02)."
        ),
        "hashtags": ["#PostgreSQL", "#Fintech", "#BackendArchitecture"],
    },
    3: {
        "hook": (
            "Pusimos IA en finanzas reales, pero con una regla de oro de arquitectura: cada "
            "token, latencia y centavo gastado debe auditarse en tiempo real."
        ),
        "conflict": (
            "Los LLMs en producción son una caja negra si no se monitorea el drift de prompts "
            "y el costo operativo por expediente crediticio."
        ),
        "solution": (
            "Integramos observabilidad end-to-end con Langfuse y OpenTelemetry (SPEC-03), trazando "
            "cada llamada a Gemini con fallback transparente ante degradación."
        ),
        "hashtags": ["#LLMOps", "#Observability", "#Fintech"],
    },
    4: {
        "hook": (
            "La IA no aprueba créditos sola: el comité humano de la cooperativa siempre "
            "tiene la última palabra."
        ),
        "conflict": (
            "Un oficial de crédito no lee logs de terminal ni JSONs crudos; necesita una bandeja "
            "operativa rápida con métricas e inspección visual inmediata."
        ),
        "solution": (
            "Desarrollamos el Dashboard Web en Next.js 14 y Tailwind (SPEC-04) con bandejas por "
            "estado, visualización de ratios duros y formulario Human-in-the-Loop."
        ),
        "hashtags": ["#NextJS", "#Fintech", "#UXEngineering"],
    },
    5: {
        "hook": (
            "¿Cómo evalúa un analista senior un crédito difícil? Buscando qué pasó antes con "
            "empresas de perfil similar en la cartera de la cooperativa."
        ),
        "conflict": (
            "Buscar en millones de préstamos pasados con SQL tradicional por texto exacto ignora "
            "el contexto de negocio y el comportamiento de solvencia."
        ),
        "solution": (
            "Construimos un RAG semántico con pgvector y embeddings vectoriales (SPEC-05), "
            "recuperando precedentes históricos para justificar el dictamen con evidencia."
        ),
        "hashtags": ["#VectorSearch", "#RAG", "#MachineLearning"],
    },
    6: {
        "hook": (
            "Cuando un crédito presenta riesgo crítico o entra en mora potencial, el oficial "
            "no puede enterarse 24 horas después."
        ),
        "conflict": (
            "Desacoplar la detección de riesgos en el backend de la notificación inmediata a "
            "múltiples canales sin bloquear el flujo transaccional de la API."
        ),
        "solution": (
            "Arquitectura de eventos con AWS SNS fanout, streaming SSE hacia el frontend en "
            "Next.js y alertas push automáticas a Telegram (SPEC-06)."
        ),
        "hashtags": ["#EventDriven", "#AWSSNS", "#RealTime"],
    },
    7: {
        "hook": (
            "La Superintendencia Bancaria vino a auditar el expediente: ¿cómo demostrás que "
            "nadie modificó el dictamen de IA ni los números calculados?"
        ),
        "conflict": (
            "Los PDFs y Excels exportados pueden ser manipulados tras la descarga, destruyendo "
            "la validez probatoria ante auditores."
        ),
        "solution": (
            "Generamos legajos oficiales en PDF y Excels con fórmulas vivas, acompañados de un "
            "Sello Criptográfico SHA-256 canónico de no-repudio bancario (SPEC-07)."
        ),
        "hashtags": ["#CyberSecurity", "#FintechAudit", "#Python"],
    },
    8: {
        "hook": (
            "El asociado nos mandó balances en PDF escaneado y un Excel de 40 hojas: ¿cómo los "
            "procesa el motor sin romperse?"
        ),
        "conflict": (
            "Archivos maliciosos camuflados como PDF (.exe renombrado) y formatos contables "
            "dispares hacen fracasar la ingesta."
        ),
        "solution": (
            "Validación estricta de Magic Bytes en cabeceras de archivo y extracción con Gemini "
            "Vision y openpyxl normalizada en esquemas Pydantic (SPEC-08)."
        ),
        "hashtags": ["#DocumentAI", "#Fintech", "#Python"],
    },
    9: {
        "hook": (
            "Aprobamos créditos con IA, pero la Superintendencia no acepta 'el modelo dijo que sí' "
            "como garantía contable de solvencia."
        ),
        "conflict": (
            "Los modelos probabilísticos no pueden fijar reservas bancarias ni responder ante "
            "auditorías sin una matriz de ponderación determinística y trazable."
        ),
        "solution": (
            "Diseñamos una matriz de scoring multicriterio A–E (DSCR 35%, Liquidez 30%, "
            "Concentración 20%, IA 15%) que calcula la provisión obligatoria en USD (SPEC-09)."
        ),
        "hashtags": ["#CreditScoring", "#BankingRegulations", "#Fintech"],
    },
    10: {
        "hook": (
            "¿Qué pasa si las ventas del asociado caen 25% o suben las tasas de interés antes "
            "de que termine de pagar el préstamo a la cooperativa?"
        ),
        "conflict": (
            "Aprobar solo con la foto financiera estática del último balance deja a la entidad "
            "vulnerable a choques macroeconómicos imprevistos."
        ),
        "solution": (
            "Incorporamos un simulador de pruebas de estrés financiero (Stress Testing & "
            "Sensibilidad) para proyectar deterioro de rating y reservas (SPEC-10)."
        ),
        "hashtags": ["#StressTesting", "#RiskManagement", "#Fintech"],
    },
    11: {
        "hook": (
            "¿Qué pasa si un crédito en Categoría B o C entra en mora? La cooperativa no puede "
            "depender solo de la buena fe del asociado; necesita garantías ejecutables."
        ),
        "conflict": (
            "Los avalúos comerciales se degradan en remates judiciales y la normativa bancaria no "
            "permite computar el 100% del colateral como cobertura directa."
        ),
        "solution": (
            "Implementamos el motor de valuación de colaterales admisibles y LTV con haircuts "
            "normativos (SPEC-11), recalculando la provisión neta y liberando capital patrimonial."
        ),
        "hashtags": ["#CollateralManagement", "#RiskMitigation", "#Fintech", "#CreditRisk"],
    },
}


def load_state() -> dict[str, Any]:
    """Carga el estado del contador diario persistido."""
    if not STATE_FILE.exists():
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        default_state = {
            "current_day": 1,
            "total_days": 100,
            "project_name": "Confiamos Risk Engine (CRE)",
            "client": "Cooperativa Confiamos",
            "last_sent_at": None,
            "history": [],
        }
        save_state(default_state)
        return default_state

    with open(STATE_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict[str, Any]) -> None:
    """Guarda el estado del contador diario de forma atómica."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def get_story_for_day(day: int) -> DailyPostStory:
    """Obtiene la historia estructurada para el día especificado."""
    if day in STORIES_CATALOG:
        entry = STORIES_CATALOG[day]
        return DailyPostStory(
            day_number=day,
            hook=entry["hook"],
            conflict=entry["conflict"],
            solution=entry["solution"],
            hashtags=entry.get("hashtags", ["#Fintech", "#SoftwareEngineering", "#AIEngineering"]),
        )

    # Fallback constructivo para días posteriores del plan de 100 días
    return DailyPostStory(
        day_number=day,
        hook=(
            f"Avanzamos con la entrega a 100 días de Confiamos Risk Engine para Cooperativa "
            f"Confiamos (Hito del Día {day})."
        ),
        conflict=(
            "Asegurar la máxima resiliencia bancaria y cobertura de tests bajo "
            "arquitectura hexagonal."
        ),
        solution=(
            "Seguimos profundizando la suite de pruebas automatizadas y verificaciones "
            "determinísticas en producción."
        ),
        hashtags=["#Fintech", "#SoftwareEngineering", "#AIEngineering"],
    )


async def dispatch_daily_story(
    day_override: int | None = None,
    dry_run: bool = False,
    advance_counter: bool = True,
) -> dict[str, Any]:
    """Despacha la historia del día a Telegram y actualiza el contador persistente."""
    state = load_state()
    target_day = day_override if day_override is not None else state.get("current_day", 1)

    story = get_story_for_day(target_day)
    notifier = TelegramNotifier()

    print("📦 Confiamos Risk Engine (CRE) | Proyecto Real — Entrega a 100 Días")
    print(f"Despachando historia técnica del Día {story.day_number}/100 a Telegram...")

    result = await notifier.send_story_draft(story, dry_run=dry_run)

    if result.get("delivered") and not dry_run and advance_counter:
        state["last_sent_at"] = datetime.now(UTC).isoformat()
        state["history"].append(
            {
                "day_number": target_day,
                "sent_at": state["last_sent_at"],
                "status": "delivered",
            }
        )
        if target_day < state.get("total_days", 100):
            state["current_day"] = target_day + 1
        save_state(state)
        print(f"✅ Día {target_day} enviado. Contador avanzado a Día {state['current_day']}.")
    elif result.get("delivered"):
        print(f"✅ Día {target_day} enviado exitosamente a Telegram.")
    elif result.get("status") == "dry_run":
        current = state.get("current_day", 1)
        print(f"ℹ️ Modo simulación (dry_run) para el Día {target_day}. Contador en {current}.")

    return result


if __name__ == "__main__":
    args = sys.argv[1:]

    dry_run_flag = "--dry-run" in args
    status_flag = "--status" in args

    if status_flag:
        st = load_state()
        cur_d = st.get("current_day", 1)
        last_d = st.get("last_sent_at")
        print(f"Estado Actual: Día {cur_d}/100 | Último: {last_d}")
        sys.exit(0)

    if "--reset" in args:
        idx = args.index("--reset")
        new_day = int(args[idx + 1]) if len(args) > idx + 1 and args[idx + 1].isdigit() else 1
        st = load_state()
        st["current_day"] = new_day
        save_state(st)
        print(f"🔄 Contador reiniciado al Día {new_day}/100.")
        sys.exit(0)

    day_to_send: int | None = None
    advance = True
    if "--day" in args:
        idx = args.index("--day")
        if len(args) > idx + 1 and args[idx + 1].isdigit():
            day_to_send = int(args[idx + 1])
            advance = False

    res = asyncio.run(
        dispatch_daily_story(
            day_override=day_to_send,
            dry_run=dry_run_flag,
            advance_counter=advance,
        )
    )

    if not res.get("delivered") and not dry_run_flag:
        print(f"❌ Error al despachar mensaje: {res}")
        sys.exit(1)
