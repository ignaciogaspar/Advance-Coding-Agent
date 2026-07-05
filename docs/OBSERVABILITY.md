# Observabilidad

## Qué se registra

Cada corrida crea una **traza** (`trace_id`) con un árbol de spans anidados:

```
trace (cli-run / demo-X)
├── orchestrator-decide-1        (plan)      ← decisión JSON del agente principal
├── subagent:researcher          (subagent)
│   ├── tool:rag_search          (tool)      ← retrieval RAG (docs + scores)
│   └── llm-call                 (generation)← prompt, modelo, tokens, costo, latencia
├── orchestrator-decide-2        (plan)
└── final                                    ← status + totales
```

Información mínima registrada (cumple la consigna):

| Campo | Dónde |
|-------|-------|
| Prompts | `prompt_preview` en eventos `llm` |
| Modelo | `model` |
| Llamadas al LLM | eventos `llm` / `totals.llm_calls` |
| Tools invocadas | eventos `tool` / `totals.tool_calls` |
| Documentos recuperados | evento `retrieval` (ids + scores) |
| Búsquedas web | evento `web_search` |
| Iteraciones | spans `orchestrator-decide-N` + iteraciones de subagente |
| Errores | `totals.errors` + campo `error` en cada span |
| Latencia | `latency_s` en cada span |
| Tokens | `in_tokens` / `out_tokens` / `totals.tokens` |
| Costo estimado | `cost_usd` (tabla de precios en `observability.py`) |
| Resultado final | evento `final` |

## Langfuse (recomendado)

1. Creá una cuenta en https://cloud.langfuse.com (o self-host) y un proyecto.
2. Copiá las claves a `.env`:

   ```env
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_HOST=https://cloud.langfuse.com
   ```

3. Corré cualquier demo o pedido, por ejemplo:

   ```bash
   python tests/demo_4_observability.py
   # o
   python main.py "Analizá la arquitectura de la API y resumí los endpoints"
   ```

4. Abrí el dashboard de Langfuse → sección **Traces**. Vas a ver la traza con su
   árbol de spans, los tokens, el costo y la latencia por paso.

### Capturas (entregable #7)

Capturas reales de Langfuse Cloud (región US), en `docs/screenshots/`:

| Captura | Qué muestra |
|---------|-------------|
| `langfuse_trace_list.png` | Lista de traces: `rag-ingest`, `demo-1-rag`, `demo-2-mem-s1/s2`, `demo-3-block`, `demo-4-observability` (2026-07-05) |
| `langfuse_trace_detail.png` | Traza completa `demo-4-observability` con el árbol de spans expandido |
| `langfuse_generation.png` | Detalle de una generación `llm-call`: modelo, tokens, costo y latencia |
| `langfuse_dashboard.png` | Dashboard de métricas agregadas del proyecto |

Además, `docs/results/` contiene el **export JSON completo** de los 88 eventos
de todas las trazas, descargado desde Langfuse (evidencia auditable cruda).

## Traza documentada: `demo-4-observability`

Análisis campo por campo de la traza `a97491ba-da43-4938-bad7-6861be248e20`
(corrida real del 2026-07-05 con `gpt-4o-mini`, visible en las capturas y en el
export de `docs/results/`). Pedido: *"Resumí cómo se declara un request body en
FastAPI (con fuentes RAG)"*.

| Campo exigido | Valor registrado en la traza |
|---------------|------------------------------|
| **Prompts** | Visibles en el `input` de cada generación `llm-call`: system prompt del orquestador (con la memoria del proyecto inyectada), system prompts de `explorer` y `researcher`, y los mensajes de cada turno |
| **Modelo utilizado** | `gpt-4o-mini` (chat) y `text-embedding-3-small` (embedding de la consulta RAG) |
| **Llamadas al LLM** | 8 generaciones `llm-call` |
| **Tools invocadas** | 2: `tool:read_file` (`app/routers/tasks.py`, por el explorer) y `tool:rag_search` (por el researcher) |
| **Documentos recuperados** | 4 chunks con scores: `02_request_body_pydantic.md#0` (0.588), `02_request_body_pydantic.md#2` (0.514), `04_response_model.md#0` (0.472), `SOURCES.md#0` (0.451) — evento `retrieval` |
| **Búsquedas web** | 0 — el RAG aportó evidencia SUFICIENTE (scores > `min_score` 0.20), por lo que el researcher **no** recurrió al fallback web, cumpliendo la política RAG-first |
| **Iteraciones** | 3 turnos del orquestador (`orchestrator-decide-1/2/3`: delegate→explorer, delegate→researcher, cierre) + las iteraciones internas de cada subagente (razonar→tool→observar) |
| **Errores** | 0 (`totals.errors = 0`) |
| **Latencia** | ~23.8 s de reloj (19:53:05 → 19:53:29); por paso: explorer 5.0 s, researcher 8.1 s (máximo), decisiones del orquestador 2.3/1.6/6.8 s |
| **Tokens** | 7 409 en total (desglose entrada/salida por generación en cada `llm-call`) |
| **Costo estimado** | US$ 0.001595 (calculado por el agente con la tabla de precios de `observability.py`; Langfuse calcula el suyo en paralelo) |
| **Resultado final** | El researcher produjo el resumen correcto con fuentes RAG. La corrida cerró con `status: blocked` porque el parser del orquestador no toleraba saltos de línea literales dentro del JSON de la decisión `finish` — bug detectado gracias a esta traza y corregido en `orchestrator.py` (`json.loads(..., strict=False)` + rescate por regex). Ver `docs/REFLECTION.md` |

## Sin Langfuse (fallback local)

Si no configurás Langfuse, **nada se rompe**: la traza completa se escribe en
`data/traces.jsonl` (un evento JSON por línea). Podés inspeccionarla:

```bash
tail -f data/traces.jsonl
# o resumirla:
python tests/demo_4_observability.py
```

Este log local sirve como evidencia auditable equivalente cuando no hay dashboard.
