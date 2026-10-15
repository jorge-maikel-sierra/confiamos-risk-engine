# Confiamos Risk Engine (CRE)

> Motor determinístico y asistido por IA para evaluación y suscripción de riesgo crediticio en PyMEs y asociados comerciales de **Cooperativa Confiamos**.

---

## 🏛️ Arquitectura del Monorepo

```text
/
├── .specs/             # Especificaciones formales (Spec-Driven Development)
│   └── 01-credit-risk-engine.md
├── apps/
│   ├── api/            # Backend en FastAPI + LangGraph + Google GenAI SDK
│   │   ├── src/        # Lógica de cálculo financiero y endpoints REST
│   │   └── tests/      # Tests unitarios y de integración con pytest
│   └── web/            # Frontend en Next.js (Dashboard + Portfolio de avance)
├── packages/           # Librerías y esquemas compartidos
├── docker-compose.yml  # PostgreSQL 16 con extensión pgvector
└── AGENTS.md           # Reglas inquebrantables de gobierno y desarrollo
```

---

## 🚀 Inicio Rápido

### 1. Requisitos Previos
* Docker & Docker Compose
* Python 3.11+
* Node.js 18+

### 2. Base de Datos Local
```bash
docker compose up -d
```

### 3. Backend (API)
```bash
cd apps/api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pytest
uvicorn src.main:app --reload --port 8000
```
