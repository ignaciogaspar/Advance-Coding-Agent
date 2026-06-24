# TP Final — Coding Agent Avanzado (multi-agente)

Sistema de agentes de IA para resolver tareas de código sobre **FastAPI**,
construido a partir del coding agent del TP en clase y **sin frameworks de
orquestación** (nada de LangChain / LangGraph / CrewAI / AutoGen). Toda la
coordinación, el RAG, la memoria, las políticas y la observabilidad están hechos
a mano sobre la API de OpenAI.

**Autores:** Marco Schenker · Ignacio Gaspar

---

## 1. Tabla de contenidos

- [2. Instalación](#2-instalación)
- [3. Configuración](#3-configuración)
- [4. Ejecución](#4-ejecución)
- [5. Caso de uso](#5-caso-de-uso)
- [6. Arquitectura](#6-arquitectura)
- [7. Base RAG](#7-base-rag)
- [8. Memoria, contexto y seguridad](#8-memoria-contexto-y-seguridad)
- [9. Observabilidad](#9-observabilidad)
- [10. Evidencia de pruebas](#10-evidencia-de-pruebas)
- [11. Sistema de plugins (extra)](#11-sistema-de-plugins-extra)
- [12. Reflexión final](#12-reflexión-final)

---

## 2. Instalación

Requiere Python 3.10+.

```bash
cd Advance-Coding-Agent
python -m venv .venv && source .venv/bin/activate    # opcional
pip install -r requirements.txt
```

Dependencias (todas son librerías puntuales, no frameworks de agentes):
`openai` (LLM + embeddings), `requests` (búsqueda web Tavily), `PyYAML` (config),
`numpy` (similitud coseno del vector store), `langfuse` (observabilidad).

## 3. Configuración

1. Copiá `.env.example` a `.env` y completá tus claves:

   ```env
   OPENAI_API_KEY=sk-...
   TAVILY_API_KEY=tvly-...
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_HOST=https://cloud.langfuse.com
   ```

2. Revisá `agent.config.yaml` (workspace, modelos, límites, RAG, **políticas de
   seguridad**). La configuración **se valida antes de cada tool call**.

3. Construí el índice RAG (una sola vez):

   ```bash
   python -m advanced_agent.rag.ingest               # embeddings OpenAI (con clave)
   python -m advanced_agent.rag.ingest --mock        # embeddings mock (sin clave, para probar el pipeline)
   ```

> **Sin claves de API** el sistema sigue funcionando en **modo mock** determinista
> (LLM y embeddings simulados), pensado para correr las pruebas y la CI sin gastar
> créditos. Con claves reales usa OpenAI/Tavily/Langfuse de verdad.

## 4. Ejecución

```bash
# Pedido único
python main.py "Analizá la arquitectura de la API y resumí los endpoints"

# REPL interactivo
python main.py

# Listar las tools descubiertas por el sistema de plugins
python main.py --tools

# Modo mock (sin red ni claves) + estado final en JSON
python main.py --mock --state "Resumí cómo se declara un request body en FastAPI"
```

Pruebas:

```bash
pytest -q tests/test_offline.py     # tests unitarios offline (7)
python tests/demo_1_rag.py          # RAG con fuentes recuperadas
python tests/demo_2_memory.py       # memoria persistente entre sesiones
python tests/demo_3_block.py        # falta de evidencia → se detiene y pide ayuda
python tests/demo_4_observability.py# traza completa registrada
```

---

## 5. Caso de uso

**Ecosistema elegido:** FastAPI (framework web de Python) + Pydantic.

**Repositorio objetivo:** `example_project/` — una **To-Do API** en FastAPI con
modelos Pydantic, un `APIRouter` y endpoints CRUD (incluida en este repo).

**Objetivo concreto:** que el agente pueda (a) **analizar** una API FastAPI
desconocida y producir un reporte de arquitectura, dependencias y endpoints, y
(b) **extender** la API agregando funcionalidad (p. ej. un endpoint nuevo o
validaciones), apoyándose en la documentación oficial de FastAPI vía RAG.

**Criterio de éxito:**

- El Explorer identifica correctamente la estructura (app, router, modelos).
- El Researcher responde preguntas de FastAPI **citando fragmentos del RAG**, y
  recurre a la web sólo si el RAG no alcanza.
- Para cambios de código, el Implementer escribe respetando las políticas, el
  Tester valida y el Reviewer confirma que se cumplió el pedido.
- Toda la corrida queda **trazada** en la herramienta de observabilidad.

---

## 6. Arquitectura

Diagrama y descripción completos en [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
Resumen:

```
                    ┌─────────────────────────────┐
   pedido  ───────► │   Orchestrator (agente       │
   usuario          │   principal)                 │
                    │  - plan/decisión en JSON     │
                    │  - mantiene el estado        │
                    │  - resume contexto largo     │
                    │  - anti-loop de delegación   │
                    └──────────────┬──────────────┘
                                   │ delega (1 subagente por paso)
        ┌──────────┬───────────────┼───────────────┬──────────┐
        ▼          ▼               ▼               ▼          ▼
   Explorer   Researcher      Implementer       Tester    Reviewer
   (lee repo) (RAG→web)       (escribe código)  (tests)   (valida)
        └──────────┴───────────────┴───────────────┴──────────┘
                          │ usan tools (con políticas)
                          ▼
   ToolRegistry → read_file · write_file · run_command · list_files
                  · web_search · rag_search · memory_read · memory_write
                          │
        ┌─────────────────┼──────────────────┬───────────────┐
        ▼                 ▼                  ▼               ▼
   TaskState         RagIndex          ProjectMemory      Tracer
 (estado compart.) (vector store)     (memoria JSON)   (Langfuse+JSONL)
```

**Agente principal (`Orchestrator`).** Recibe la tarea, mantiene el `TaskState`,
y en cada turno le pide al LLM una decisión en JSON: `delegate` (a qué subagente y
con qué instrucción), `finish` (respuesta final) o `need_user` (pedir ayuda).
Integra cada resultado en el estado y decide el siguiente paso, con tope de
delegaciones y detección de delegaciones repetidas.

**Subagentes (`agents/subagents.py`).** Cada uno hereda de `BaseAgent` (el loop
agéntico razonar→tool→observar) y se distingue por su system prompt y por el
**subconjunto de tools** que tiene habilitado (menor privilegio):

| Subagente | Responsabilidad | Tools habilitadas |
|-----------|-----------------|-------------------|
| Explorer | Arquitectura, deps, convenciones, archivos clave | list_files, read_file, memory_* |
| Researcher | RAG primero, web como fallback | rag_search, web_search, memory_* |
| Implementer | Cambios de código | read_file, write_file, list_files, rag_search, memory_* |
| Tester | Tests, build, lint, logs | read_file, list_files, run_command, memory_read |
| Reviewer | Valida que se cumpla el pedido | read_file, list_files, memory_* |

**Estado compartido (`core/state.py`).** `TaskState` registra el pedido original,
el avance, los resultados de subagentes, las **fuentes consultadas etiquetadas por
origen** (repo / memory / rag / web / inference), los archivos modificados, las
observaciones y las métricas. Es serializable a JSON en cualquier momento.

## 7. Base RAG

Documentación completa en [`docs/RAG.md`](docs/RAG.md). Resumen:

- **Fuentes:** 6 documentos derivados de la **documentación oficial de FastAPI**
  (first steps, request body/Pydantic, dependencias, response_model, testing &
  errores, routers/estructura) + un `SOURCES.md`. Ver `rag_corpus/`.
- **Chunking:** por caracteres (800) con solape (150), cortando en límites de
  párrafo/oración (`rag/index.py::chunk_text`).
- **Embeddings:** OpenAI `text-embedding-3-small` (o mock determinista sin clave).
- **Almacenamiento vectorial:** archivo JSON (`data/rag_index.json`) con los
  vectores; recuperación por **similitud coseno** con numpy. Sin DB externa.
- **Recuperación:** `top_k` configurable, `min_score` para decidir si la evidencia
  es suficiente. La tool `rag_search` **muestra los documentos, los scores y los
  fragmentos citados**, y los registra en el estado como origen `rag`.
- **Política de búsqueda:** el Researcher consulta **primero el RAG**; sólo si la
  evidencia es débil (score bajo) pasa a `web_search`, priorizando docs oficiales.

## 8. Memoria, contexto y seguridad

**Memoria persistente (`memory/project_memory.py`).** Distinta del historial de
conversación. Guarda por secciones: `architecture`, `key_files`, `dependencies`,
`commands`, `conventions`, `decisions`, `bugs`, `session_summaries`. Persiste en
`data/project_memory.json` y se carga al inicio de cada sesión.

**Manejo de contexto largo.** El orquestador **no manda el repo ni el historial
completo** en cada turno: inyecta sólo `TaskState.brief()` (plan + últimos avances
+ archivos + observaciones). Si el estado supera el presupuesto de tokens, lo
**resume** conservando decisiones importantes (`_maybe_summarize`).

**Detección de loops (`agents/base_agent.py::LoopDetector`).** Si la misma
`(tool, args)` o el mismo resultado de error se repite N veces seguidas, se
declara loop: el agente **cambia de estrategia, replanifica o se detiene**.

**Falta de evidencia.** Los subagentes pueden responder `FALTA EVIDENCIA`
explicando qué intentaron, qué falta y qué necesitan; el orquestador entonces usa
`need_user` (estado `blocked`) en vez de inventar una solución.

**Políticas de seguridad (`core/config.py::PolicyEngine`).** Se validan **antes de
cada tool call** en el único punto de ejecución (`ToolRegistry.execute`):

| Política | Ejemplos (de `agent.config.yaml`) |
|----------|-----------------------------------|
| Lectura (deny) | `.env`, `**/*.pem`, `**/*.key`, `secrets/**` |
| Escritura (deny) | `.github/**`, `**/*.lock`, `package-lock.json` |
| Comandos (deny) | `rm -rf`, `git push`, `mkfs`, fork bomb |
| Aprobación | `pip install`, `npm install`, `git commit`, `curl` |

Además, todo path se confina al `workspace` (defensa contra path traversal).

## 9. Observabilidad

`core/observability.py` integra **Langfuse**. Con `LANGFUSE_*` configuradas, cada
corrida crea una traza con el árbol de spans (orquestador → subagentes → tools →
LLM). Sin claves, **no falla**: cae a un log local `data/traces.jsonl` que también
es una traza completa y auditable.

Información registrada (mínimo exigido): **prompts, modelo, llamadas LLM, tools
invocadas, documentos recuperados, búsquedas web, iteraciones, errores, latencia,
tokens, costo estimado y resultado final**. Ver capturas/instrucciones en
[`docs/OBSERVABILITY.md`](docs/OBSERVABILITY.md).

## 10. Evidencia de pruebas

Las cuatro demos cubren lo pedido por la consigna. Salidas reales (modo mock) en
[`docs/EVIDENCE.md`](docs/EVIDENCE.md):

1. **`demo_1_rag.py`** — usa RAG y muestra las fuentes recuperadas (con score y
   fragmento), diferenciadas por origen.
2. **`demo_2_memory.py`** — guarda arquitectura en sesión 1 y un sistema nuevo la
   recuerda en sesión 2 (persistencia entre sesiones).
3. **`demo_3_block.py`** — pedido sin evidencia → el agente se detiene (`blocked`)
   y explica qué falta y qué necesita.
4. **`demo_4_observability.py`** — imprime el resumen de una traza completa y la
   envía a Langfuse (o al log local).

`tests/test_offline.py` agrega 7 tests unitarios (políticas, path traversal,
descubrimiento de plugins, chunking, retrieval RAG, loop detector, memoria).

## 11. Sistema de plugins (extra)

Implementado. Cada tool es una subclase de `Tool` (`tools/base.py`) con interfaz
común: **nombre, descripción, schema de parámetros, función de ejecución y
política de permisos**. El `ToolRegistry` **descubre e instancia automáticamente**
todas las tools de `tools/plugins/`. Agregar una tool nueva es soltar un archivo
en esa carpeta — **sin tocar el núcleo del harness**.

## 12. Reflexión final

Ver [`docs/REFLECTION.md`](docs/REFLECTION.md): qué funcionó bien, qué falló,
dónde hubo loops o falta de evidencia, y qué mejoraríamos.

---

### Nota de seguridad

Las claves de OpenAI/Tavily compartidas para este TP quedaron expuestas en texto
plano; **conviene rotarlas**. El código nunca las hardcodea: las lee de variables
de entorno / `.env` (y `.env` está denegado por las políticas de lectura).