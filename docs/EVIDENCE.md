# Evidencia de pruebas

Salidas **reales** de las demos (corridas en modo mock, sin claves, para que sean
reproducibles). Con `OPENAI_API_KEY`/`TAVILY_API_KEY`/`LANGFUSE_*` configuradas,
las mismas demos llaman a los servicios reales.

`pytest -q tests/test_offline.py` → **7 passed** (políticas, path traversal,
descubrimiento de plugins, chunking, retrieval RAG, loop detector, memoria).

---

## Demo 1 — RAG con fuentes recuperadas

`python tests/demo_1_rag.py`

```
======================================================================
DEMO 1 — RAG con fuentes recuperadas
======================================================================

--- RESPUESTA ---
Resumen entregado con evidencia del RAG (request body Pydantic + response_model).

--- FUENTES POR ORIGEN ---

[rag] (4)
  - SOURCES.md  score=0.4619
      «# Fuentes del corpus RAG ... El corpus se especializa en FastAPI ...»
  - SOURCES.md  score=0.4146
      «... 04_response_model.md | response_model, filtrado de salida ...»
  - 02_request_body_pydantic.md  score=0.3927
      «# FastAPI — Request Body with Pydantic. When a client sends data ...»
  - 06_project_structure_routers.md  score=0.3272
      «# FastAPI — Bigger Applications, Routers and Project Structure ...»

Trace: 0fedca49-... | log: data/traces.jsonl
```

**Lectura:** el Researcher consultó el RAG y devolvió 4 fragmentos con su fuente
y score, registrados con origen `[rag]`. (En mock el ranking es aproximado; con
embeddings reales de OpenAI, `02_request_body_pydantic.md` y `04_response_model.md`
quedan primeros.)

---

## Demo 2 — Memoria persistente entre sesiones

`python tests/demo_2_memory.py`

```
>>> SESIÓN 1: el Explorer detecta y guarda la arquitectura en memoria
Memoria persistida en disco:
[architecture]   - API FastAPI con router /tasks y modelos Pydantic
[key_files]      - app/main.py, app/routers/tasks.py, app/models.py
[session_summaries] - 2026-06-24 ... → Arquitectura detectada y persistida ...

>>> SESIÓN 2: un sistema NUEVO arranca y ya conoce el proyecto
Lo que el sistema nuevo recuerda al arrancar:
[architecture]   - API FastAPI con router /tasks y modelos Pydantic
[key_files]      - app/main.py, app/routers/tasks.py, app/models.py

[OK] La memoria del proyecto persistió entre sesiones.
```

**Lectura:** un sistema completamente nuevo (estado fresco) arranca y ya conoce la
arquitectura porque la leyó de `data/project_memory.json`. La memoria sobrevive a
la sesión.

---

## Demo 3 — Falta de evidencia: el agente se detiene y pide ayuda

`python tests/demo_3_block.py`

```
--- RESPUESTA FINAL ---
No tengo evidencia suficiente para implementar la integración con el sistema XYZ.
Intenté: búsqueda en RAG (sin resultados). Falta: documentación oficial o specs
del sistema XYZ. Necesito: que me proporciones esa documentación o relajes el alcance.

Estado final: blocked

--- OBSERVACIONES (por qué se detuvo) ---
  - RAG con baja evidencia: el Researcher debería ir a la web.
  - [researcher] BLOQUEADO: FALTA EVIDENCIA: ni el RAG ni la documentación cubren ...
  - El orquestador pidió ayuda al usuario (falta evidencia/ambigüedad).

[OK] El agente reconoció la falta de evidencia y pidió ayuda en lugar de inventar.
```

**Lectura:** ante un pedido imposible de resolver con la evidencia disponible, el
Researcher declara `FALTA EVIDENCIA`, el orquestador toma la acción `need_user`,
el estado queda `blocked`, y la respuesta **explica qué intentó, qué falta y qué
necesita** — exactamente lo pedido por la consigna.

---

## Demo 4 — Traza completa en la herramienta de observabilidad

`python tests/demo_4_observability.py`

```
Langfuse activo: False  |  modo mock: True
Trace ID: 90e23008-...
Eventos registrados (13): {'warn':1,'llm':5,'plan':2,'retrieval':1,'tool':2,'subagent':1,'final':1}

--- Información mínima registrada ---
  modelo(s):        ['gpt-4o-mini[mock]', 'text-embedding-3-small[mock]']
  llamadas LLM:     5
  tools invocadas:  1
  retrievals RAG:   1
  búsquedas web:    0
  errores:          0
  tokens (aprox):   1557
  costo estimado:   $0.0
  latencia total:   0.038s
```

**Lectura:** la traza registra todo el mínimo exigido: prompts, modelo, llamadas
LLM, tools, retrievals RAG, búsquedas web, iteraciones, errores, latencia, tokens,
costo y resultado final. Con `LANGFUSE_*` configuradas, el mismo árbol de spans
aparece en el dashboard de Langfuse (ver `docs/OBSERVABILITY.md`).

---

## Verificación del motor de políticas (seguridad)

Ejecutando tools a través del `ToolRegistry` (la puerta de ejecución):

```
1. read .env                 → DENEGADO por política: lectura denegada por '.env'
2. write package-lock.json   → DENEGADO por política: escritura denegada por 'package-lock.json'
3. run 'rm -rf /tmp/x'       → DENEGADO por política: comando denegado por 'rm -rf'
4. run 'pip install evil'    → requiere aprobación → auto-deny en modo no interactivo
5. read app/main.py          → OK (devuelve el contenido)
6. write app/new.py          → OK (escrito)
7. run 'echo hello'          → OK (hello, exit=0)
```

La validación ocurre **antes** de ejecutar cada tool, como exige la consigna.
