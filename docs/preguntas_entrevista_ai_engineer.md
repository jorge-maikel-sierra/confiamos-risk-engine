# Guía de Entrevista: AI Engineer (Senior / Tech Lead)
### Respuestas Estratégicas Basadas en la Arquitectura Real de *Confiamos Risk Engine*

Esta guía compila las 5 preguntas técnicas y de diseño de sistemas más frecuentes en procesos de selección para roles de **AI Engineer**, con respuestas estructuradas bajo el método **STAR** (Situación, Tarea, Acción, Resultado) basadas en las decisiones de diseño del proyecto *Confiamos Risk Engine*.

---

## 1. RAG y Mitigación de Alucinaciones en Entornos Críticos

> **Pregunta del Reclutador:**  
> *"¿Cómo diseñás e implementás una arquitectura RAG en producción para evitar alucinaciones cuando la decisión tiene impacto financiero o regulatorio?"*

### Enfoque Conceptual
En fintech o entornos regulados no se puede confiar ciegamente en el conocimiento implícito del LLM. La clave es el **desacoplamiento estricto entre el cálculo determinístico y la auditoría cualitativa asistida por recuperación**.

### Respuesta STAR Recomendada
* **Situación:** En *Confiamos Risk Engine*, evaluamos créditos PyME para una cooperativa financiera donde un dictamen erróneo genera pérdidas de capital o incumplimiento ante superintendencias financieras.
* **Tarea:** Diseñar un pipeline donde el modelo de lenguaje no calcule ratios a ojo ni invente precedentes de riesgo, sino que fundamente su dictamen cualitativo en evidencia histórica real.
* **Acción:**
  1. **Separación de responsabilidades:** Calculamos métricas financieras duras (DSCR, Liquidez Corriente, Runway) con algoritmos determinísticos puros en Python antes de tocar cualquier modelo de IA.
  2. **Retrieval semántico con `pgvector`:** Vectorizamos el perfil de riesgo de la solicitud y ejecutamos una búsqueda vectorial por similitud coseno (`<=>` nativo en PostgreSQL) sobre la tabla de créditos históricos.
  3. **Inyección contextual controlada:** Le entregamos a Gemini las métricas precalculadas y los 3 precedentes más similares (`PAID_ON_TIME` vs `DEFAULT`), forzándolo a contrastar el caso actual contra antecedentes reales verificables.
* **Resultado:** Reducción a 0% de alucinaciones en cifras cuantitativas y justificaciones de crédito auditables con trazabilidad matemática de similitud.

---

## 2. Orquestación de Agentes con Estado y Human-in-the-Loop (HitL)

> **Pregunta del Reclutador:**  
> *"¿Cuándo justificás el uso de grafos de estado (LangGraph) frente a cadenas simples (LangChain)? ¿Cómo manejás la persistencia y la intervención humana?"*

### Enfoque Conceptual
Las cadenas lineales (chains/DAGs rígidos) son insuficientes cuando el flujo requiere bucles condicionales, bifurcaciones dinámicas, puntos de reanudación diferida o auditoría humana intermedia obligatoria.

### Respuesta STAR Recomendada
* **Situación:** El proceso de suscripción de crédito requiere extracción de balances, cálculo de ratios, búsqueda de precedentes, scoring regulatorio y, si el riesgo es medio o alto, intervención obligatoria de un oficial de crédito humano.
* **Tarea:** Crear un flujo orquestado capaz de pausar su ejecución en un estado exacto, esperar la revisión de un humano durante horas o días, y reanudarse sin perder contexto.
* **Acción:**
  1. Implementamos **LangGraph (`StateGraph`)** con un estado fuertemente tipado (`CreditUnderwritingState`).
  2. Configuramos un checkpointer persistente y definimos interrupciones antes del nodo de revisión humana (`interrupt_before=["human_review"]`).
  3. Si el scorecard arroja necesidad de revisión o rechazo técnico, el grafo se detiene, persiste el snapshot en base de datos y emite eventos en tiempo real al Dashboard Web.
  4. Cuando el oficial envía su resolución vía API REST, el use case recupera el hilo (`thread_id`) y reanuda el grafo para emitir el dictamen final.
* **Resultado:** Flujo asíncrono resiliente a caídas de servidor, compatible con procesos regulatorios de cuatro ojos (*four-eyes principle*).

---

## 3. Observabilidad, Evaluación y LLMOps en Producción

> **Pregunta del Reclutador:**  
> *"¿Cómo monitoreás, evaluás y controlás los costos y la latencia de tus modelos de IA una vez desplegados en producción?"*

### Enfoque Conceptual
"No se puede optimizar lo que no se mide". Una aplicación con LLMs requiere observabilidad de caja blanca: rastreo de llamadas individuales, descomposición de latencias (retrieval vs inferencia), conteo exacto de tokens y auditoría de calidad.

### Respuesta STAR Recomendada
* **Situación:** En un entorno de producción sobre Google Cloud Run, necesitábamos visibilidad total sobre los costos de tokens, tiempos de respuesta de Gemini y efectividad del motor de búsqueda vectorial.
* **Tarea:** Instrumentar observabilidad integral sin acoplar el código de negocio a un SDK propietario de telemetría.
* **Acción:**
  1. Integramos **Langfuse** mediante un puerto/adaptador desacoplado (`ITelemetryTracker` / `LangfuseTracker`).
  2. Cada ejecución del grafo genera un `trace` asociado al `application_id`, subdividido en spans tipados: `retriever` (para medir la latencia y precisión de la consulta SQL con `pgvector`) y `llm` (para medir tiempo de inferencia de Gemini).
  3. Mapeamos uso de tokens de entrada/salida y costos estimados por inferencia.
* **Resultado:** Capacidad de auditar cada rechazo o aprobación ante comités de riesgo, detectando cuellos de botella en milisegundos y manteniendo el costo por solicitud en fracciones de centavo.

---

## 4. Arquitectura de Software Limpia (Hexagonal) Aplicada a IA

> **Pregunta del Reclutador:**  
> *"¿Cómo estructurás una base de código de IA para evitar quedar atado a un proveedor específico de modelos o a un framework que cambie su API mañana?"*

### Enfoque Conceptual
La tasa de obsolescencia en el ecosistema de IA es altísima. Si la lógica de negocio depende directamente de `import openai` o de clases internas de LangChain, el sistema se vuelve inmantecible en meses.

### Respuesta STAR Recomendada
* **Situación:** Los modelos de IA y las bases vectoriales evolucionan continuamente (ej. migración de embeddings de OpenAI a Gemini, o de Pinecone a pgvector).
* **Tarea:** Blindar la lógica de negocio crediticia para que sea 100% agnóstica a los proveedores de nube, SDKs de IA y motores de base de datos.
* **Acción:**
  1. Diseñamos el sistema bajo **Arquitectura Hexagonal Pura (Ports & Adapters)**.
  2. Definimos puertos en la capa de Dominio: `IEmbeddingGenerator`, `IVectorSearchRepository`, `IRiskAuditor`.
  3. Los casos de uso (`start_underwriting`, `review_underwriting`) interactúan exclusivamente con estas abstracciones.
  4. En la capa de Infraestructura creamos los adaptadores concretos: `PostgresVectorSearchRepository`, `GeminiRiskAuditor` y `MockEmbeddingGenerator`.
* **Resultado:** Podemos correr tests unitarios ultrarrápidos en milisegundos sin internet ni mocks complejos, y cambiar el proveedor de LLM o vector store modificando únicamente la inyección de dependencias en el contenedor.

---

## 5. Salidas Estructuradas, Tipado Estricto y Manejo de Errores REST

> **Pregunta del Reclutador:**  
> *"¿Cómo garantizás que un LLM devuelva exactamente la estructura JSON requerida por el frontend y cómo manejás fallos de parsing o contratos en una API REST?"*

### Enfoque Conceptual
El texto libre no sirve para alimentar pipelines empresariales ni dashboards reactivos. Se requieren contratos determinísticos mediante esquemas y manejo de errores estandarizado a nivel HTTP.

### Respuesta STAR Recomendada
* **Situación:** El dashboard en Next.js 14 necesita renderizar scorecards, semáforos de riesgo y condiciones crediticias tipadas en TypeScript sin temor a que el backend devuelva campos faltantes o tipos incorrectos.
* **Tarea:** Asegurar consistencia de tipo del 100% en las respuestas del LLM y mapear cualquier fallo bajo estándares HTTP modernos.
* **Acción:**
  1. Empleamos modelos **Pydantic V2** (`CreditAuditVerdict`, `AuditConditions`) acoplados al parámetro nativo `response_schema` del SDK de Google GenAI (`gemini-2.5-flash`), garantizando que la salida sea JSON válido con tipos coercitivos.
  2. Implementamos el estándar **RFC 7807 (Problem Details)** en la API FastAPI. Si la extracción de un balance contable o una solicitud viene malformada, la API responde con encabezado `application/problem+json`, código de estado específico y detalles semánticos del error.
* **Resultado:** Eliminación total de errores de deserialización en cliente, interfaces frontend consistentes y apego a los estándares internacionales de diseño de APIs REST (RFC 9110 / RFC 7807).
