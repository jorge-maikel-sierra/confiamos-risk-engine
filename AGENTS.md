# AGENTS.md — Reglas de Ingeniería y Gobierno del Proyecto

> **Proyecto**: Confiamos Risk Engine (CRE)  
> **Cliente**: Cooperativa Confiamos  
> **Arquitectura**: Monorepo (FastAPI + Next.js + PostgreSQL + Langfuse + Gemini)

---

## 1. Filosofía de Desarrollo
1. **CONCEPTS > CODE**: Entender los fundamentos financieros y de arquitectura antes de generar código.
2. **LA MATEMÁTICA NO VA EN EL PROMPT**: Toda fórmula financiera (DSCR, Liquidez, Ratios) se calcula de forma determinística en Python puro. Los LLMs solo contextualizan y emiten razonamiento cualitativo estructurado.
3. **SPEC-DRIVEN DEVELOPMENT (SDD)**: Queda terminantemente prohibido generar código o tests si no existe un archivo `.specs/XX-nombre.md` aprobado con diagramas Mermaid previos.

---

## 2. Reglas de Diagramación Obligatoria
Todo spec técnico debe contener:
* Un `sequenceDiagram` de Mermaid que detalle el flujo de red y dependencias entre capas.
* Un `flowchart TD` de Mermaid que detalle las bifurcaciones y edge cases de la lógica algorítmica.

---

## 3. Calidad de Código y Convenciones de Git
* **Commits**: Usar exclusivamente *Conventional Commits* vinculados a la especificación:
  `feat(underwriting): implement deterministic DSCR calculator [#spec-01]`
* **Cero Atribución de IA**: No incluir `Co-Authored-By` ni referencias a asistentes de IA en los mensajes de commit.
* **Hooks de Pre-Commit**:
  * Python (`apps/api`): Formateo y linting estricto con `ruff check --fix` y `ruff format`.
  * TypeScript (`apps/web`): Formateo y linting con `prettier --write` y `eslint --fix`.
* **Testing First (TDD)**:
  * Los tests unitarios (`pytest`) se escriben antes de la implementación de la función.
  * Cobertura obligatoria del 100% sobre funciones que computen métricas de riesgo.

---

## 4. Gobernanza de Modelos e Inferencia
* **Esquemas Estrictos**: Toda llamada a Gemini debe usar Structured Outputs gobernados por modelos de **Pydantic**.
* **Observabilidad Obligatoria**: Toda inferencia debe estar envuelta con instrumentación de **Langfuse** para medir latencia, costo de tokens y trazar inputs/outputs.
