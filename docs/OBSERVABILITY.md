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

Para el entregable, sacá capturas de:

- **(a)** La lista de Traces mostrando la corrida (nombre `demo-4-observability`
  o `cli-run`).
- **(b)** El detalle de **una traza completa**, abriendo el árbol de spans
  (orquestador → subagente → tool `rag_search` → generación LLM).
- **(c)** El panel de métricas de esa generación (modelo, tokens, costo, latencia).

Guardalas en `docs/screenshots/` (por ejemplo `langfuse_trace_list.png`,
`langfuse_trace_detail.png`, `langfuse_generation.png`) y referencialas acá.

> Estas capturas requieren ejecutar el sistema con tus claves reales de OpenAI y
> Langfuse; por eso no están incluidas en la entrega base (se construyó el sistema
> sin ejecutarlo contra las APIs). El comando de arriba las genera en minutos.

## Sin Langfuse (fallback local)

Si no configurás Langfuse, **nada se rompe**: la traza completa se escribe en
`data/traces.jsonl` (un evento JSON por línea). Podés inspeccionarla:

```bash
tail -f data/traces.jsonl
# o resumirla:
python tests/demo_4_observability.py
```

Este log local sirve como evidencia auditable equivalente cuando no hay dashboard.
