# AGENTS.md — Reglas de Ingeniería y Gobierno del Proyecto

> **Proyecto**: Confiamos Risk Engine (CRE)  
> **Cliente**: Cooperativa Confiamos  
> **Arquitectura**: Monorepo (FastAPI + LangGraph + Next.js + PostgreSQL + Langfuse + Gemini)

---

## 1. Filosofía de Desarrollo
1. **CONCEPTS > CODE**: Entender los fundamentos financieros y de arquitectura antes de generar código.
2. **LA MATEMÁTICA NO VA EN EL PROMPT**: Toda fórmula financiera (DSCR, Liquidez, Runway) se calcula de forma determinística en nodos de Python puro. Los LLMs solo contextualizan y emiten dictamen cualitativo estructurado.
3. **MÁQUINAS DE ESTADO CON LANGGRAPH**: Todo flujo de crédito se modela con un `StateGraph` de LangGraph fuertemente tipado. Prohibido usar cadenas abiertas o wrappers inflados de LangChain clásico.
4. **SPEC-DRIVEN DEVELOPMENT (SDD)**: Queda terminantemente prohibido generar código o tests si no existe un archivo `.specs/XX-nombre.md` aprobado con diagramas Mermaid previos.

---

## 2. Reglas de Diagramación Obligatoria
Todo spec técnico debe contener:
* Un `stateDiagram-v2` o `sequenceDiagram` de Mermaid que detalle los nodos del StateGraph y el flujo de red.
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
* **Observabilidad Obligatoria**: Toda inferencia e iteración del StateGraph debe estar instrumentada con **Langfuse** para medir latencia, costo de tokens y trazar inputs/outputs.

---

## 5. Flujo Obligatorio de Ramas y Pull Requests (PR-First)
* **Prohibido el push directo a `main`**: Toda nueva funcionalidad o corrección debe desarrollarse en su propia rama.
* **Nomenclatura de Ramas**:
  * Features: `feat/issue-<numero>-<descripcion-corta>` (ej: `feat/issue-4-underwrite-endpoint`).
  * Fixes: `fix/issue-<numero>-<descripcion-corta>`.
* **Contrato de Pull Request**:
  * Todo PR debe vincular explícitamente el Issue que resuelve con la palabra clave `Closes #<numero>`.
  * Todo PR debe contener un resumen ejecutivo de cambios, archivos modificados y evidencia de tests aprobados.
  * Todo PR debe aprobar los checks automáticos de CI (Ruff y Pytest) en GitHub Actions antes de ser mergeado.

---

## 6. Estándar Estricto de Diseño de APIs REST (FreeCodeCamp Best Practices)
Todo endpoint expuesto en la plataforma debe cumplir sin excepción con los 10 principios REST:
1. **Recursos en Plural y Cero Verbos en URIs**:
   * Usar sustantivos en plural: `/api/v1/underwritings`, `/api/v1/credit-applications`.
   * Prohibido incluir verbos en la ruta (ej: `/api/v1/getReport` o `/api/v1/createCredit` es ILEGAL). La acción la determina el método HTTP.
2. **Semántica de Métodos HTTP**:
   * `GET`: Solo lectura, seguro e idempotente.
   * `POST`: Creación de recursos o acciones no idempotentes. Retorna `201 Created`.
   * `PUT`: Reemplazo total del recurso. Idempotente.
   * `PATCH`: Modificación parcial de campos.
   * `DELETE`: Eliminación lógica o física. Retorna `204 No Content` o `200 OK`.
3. **Códigos de Estado HTTP Estándar**:
   * Éxito: `200 OK`, `201 Created`, `204 No Content`.
   * Errores de Cliente: `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`, `409 Conflict`, `422 Unprocessable Entity` (validación Pydantic).
   * Errores de Servidor: `500 Internal Server Error`.
4. **Formato JSON Estricto y Errores Uniformes**:
   * Todo cuerpo de petición y respuesta debe ser `application/json`.
   * Los errores deben retornar una estructura estandarizada con código y mensaje claro.
5. **Versionado Obligatorio en la URI**:
   * Todo endpoint debe estar prefijado con la versión mayor: `/api/v1/...`.
6. **Agrupación y Anidación Lógica de Recursos**:
   * Recursos subordinados: `/api/v1/underwritings/{application_id}/reviews`.
7. **Paginación, Ordenamiento y Filtrado**:
   * Toda consulta de colecciones debe admitir parámetros: `?page=1&limit=20&sort=-created_at&status=APROBADO`.
8. **Seguridad y Documentación OpenAPI**:
   * Cero exposición de trazas de error (`stack traces`) en respuestas de producción.
   * Documentación OpenAPI / Swagger tipada al 100% con descripciones ricas.

---

## 7. Gobernanza de Skills de Agente (skills.sh)
* Las skills externas de soporte al desarrollo se gestionan a nivel de proyecto en `.agents/skills/`.
* Solo se instalan skills estrictamente necesarias (ej: `fastapi-patterns`) para evitar inflar el repositorio.

