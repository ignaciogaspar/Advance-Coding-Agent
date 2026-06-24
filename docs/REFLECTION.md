# Reflexión final

## Qué funcionó bien

- **Coordinación sin frameworks.** El patrón "el LLM devuelve una decisión JSON
  (`delegate`/`finish`/`need_user`) y el harness la ejecuta" resultó simple, legible
  y fácil de depurar. No hicimos falta LangChain ni similares: un `while`, un `dict`
  de subagentes y un parser de JSON tolerante alcanzan para orquestar cinco roles.
- **Separación de responsabilidades y menor privilegio.** Que cada subagente sólo
  vea su subconjunto de tools (el Explorer no escribe, el Reviewer no ejecuta
  comandos) hizo el sistema más predecible y seguro.
- **Política validada en un solo punto.** Centralizar la verificación en
  `ToolRegistry.execute` garantiza que **ninguna** tool se ejecute sin pasar por las
  políticas. Los tests lo confirman (deny de `.env`, lock files, `rm -rf`; aprobación
  de `pip install`).
- **Observabilidad con degradación elegante.** Que el tracer caiga al log local
  cuando falta Langfuse permitió desarrollar y testear todo sin depender de un
  servicio externo, sin perder la traza.
- **Modo mock determinista.** Poder correr el sistema completo sin claves (LLM y
  embeddings simulados) hizo las demos reproducibles y la verificación barata.

## Qué falló o costó

- **Embeddings mock no semánticos.** En modo mock el ranking del RAG es aproximado
  (bag-of-words con hashing): en la Demo 1, `SOURCES.md` rankeó por encima del doc
  de request body porque comparte muchas palabras clave. Con embeddings reales de
  OpenAI esto se corrige. Es una limitación del modo offline, no del pipeline.
- **Parsing de la decisión del LLM.** Los modelos a veces envuelven el JSON en
  texto o markdown; hubo que hacer el parser tolerante (extraer el primer bloque
  `{...}`). Con modelos más chicos esto es más frágil; convendría usar
  *structured outputs* / *function calling* para la decisión del orquestador.
- **Coordinación de path en el sandbox.** Borrar archivos en la carpeta montada
  estaba restringido; ajustamos las demos para *resetear* contenido en vez de
  *borrar* archivos.

## Dónde hubo loops o falta de evidencia

- **Loops:** los provocamos a propósito para validar la defensa. El `LoopDetector`
  corta cuando la misma `(tool, args)` o el mismo error se repite N veces; el
  orquestador además corta si repite la misma delegación dos veces. En la práctica,
  el riesgo real es el Tester re-corriendo `pytest` con el mismo error — por eso su
  prompt le pide diagnosticar en vez de reintentar.
- **Falta de evidencia:** la Demo 3 muestra el comportamiento deseado: ante un
  pedido sin soporte en RAG ni web, el agente **no inventa**; declara
  `FALTA EVIDENCIA`, queda `blocked` y explica qué intentó, qué falta y qué necesita.

## Qué mejoraríamos

1. **Structured outputs** para las decisiones del orquestador y subagentes (evita
   el parsing frágil del JSON).
2. **Re-ranking del RAG** (p. ej. cross-encoder) y *hybrid search* (BM25 + vectores)
   para mejorar la precisión de la recuperación.
3. **Resúmenes incrementales** del estado por subagente (no sólo global), y un
   índice de "qué archivos ya leí" para evitar relecturas redundantes.
4. **Ejecución paralela** de subagentes independientes (p. ej. Explorer y Researcher
   en simultáneo) con merge del estado.
5. **Persistir el `TaskState`** completo entre sesiones (no sólo la memoria), para
   poder reanudar tareas largas.
6. **Aprobaciones más granulares** (por patrón de comando, con allowlist de flags) y
   *dry-run* de escrituras mostrando el diff antes de aplicar.
