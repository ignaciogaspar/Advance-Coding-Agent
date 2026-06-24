# Arquitectura del sistema

## Visión general

El sistema es un **orquestador multi-agente** construido sin frameworks de
orquestación. La pieza central es un bucle de coordinación escrito a mano que,
en cada turno, le pide al LLM una **decisión estructurada en JSON** y la ejecuta.

```
Usuario
  │  pedido en lenguaje natural
  ▼
AgentSystem (system.py)  ── ensambla: config, política, estado, tracer, LLM, RAG, memoria, registry
  │
  ▼
Orchestrator (agents/orchestrator.py)        ◄── AGENTE PRINCIPAL
  │  loop de coordinación:
  │   1. _maybe_summarize()  → resume el estado si supera el presupuesto de contexto
  │   2. LLM decide: {action: delegate|finish|need_user, agent, instruction, final}
  │   3. ejecuta el subagente elegido
  │   4. integra el SubagentResult en el TaskState
  │   5. anti-loop: corta si repite la misma delegación
  │
  ├─► ExplorerAgent     ─┐
  ├─► ResearcherAgent    │  cada uno = BaseAgent (loop razonar→tool→observar)
  ├─► ImplementerAgent   │  con su system prompt y su subconjunto de tools
  ├─► TesterAgent        │
  └─► ReviewerAgent     ─┘
            │
            ▼
   ToolRegistry.execute(name, args)   ◄── ÚNICA PUERTA DE EJECUCIÓN
            │  1. valida política (read/write/command) ANTES de ejecutar
            │  2. pide aprobación si corresponde
            │  3. corre la tool dentro de un span de tracing
            ▼
   Tools (plugins): read_file, write_file, run_command, list_files,
                    web_search, rag_search, memory_read, memory_write
```

## Componentes

### Agente principal — `Orchestrator`

- **Recibe** la tarea y la guarda en `TaskState.request`.
- **Mantiene el estado general**: cada resultado de subagente se integra con
  `state.add_subagent_result()`, que también acumula las fuentes.
- **Coordina** pidiendo al LLM una decisión JSON. El parser tolera texto
  alrededor del JSON y bloques markdown.
- **Maneja contexto largo**: `_maybe_summarize()` comprime el progreso cuando el
  estado supera `context_token_budget`.
- **Anti-loop de alto nivel**: si repite la misma `(agente, instrucción)` dos
  veces seguidas, se detiene y pide ayuda (`need_user`, estado `blocked`).
- Puede **ejecutar tools directamente** (opcional) — de hecho lo hace
  indirectamente vía los subagentes, y nada impide darle tools propias.

### Subagentes — `BaseAgent` + `subagents.py`

`BaseAgent` implementa el **loop agéntico** clásico:

1. Arma `messages` con su system prompt + el brief del estado (no el repo entero).
2. Llama al LLM con su subconjunto de tools.
3. Si hay `tool_calls`, las ejecuta vía `ToolRegistry` y agrega los resultados.
4. Detecta loops con `LoopDetector` (acciones/resultados idénticos repetidos).
5. Termina cuando el LLM responde sin tool_calls, o declara `FALTA EVIDENCIA`.

Los cinco subagentes se diferencian por system prompt y por `allowed_tools`
(principio de **menor privilegio**: el Explorer no puede escribir; el Reviewer no
ejecuta comandos; etc.).

### Estado compartido — `TaskState`

Una sola instancia recorre todo el sistema (se pasa por el `ToolContext`).
Registra lo que pide la consigna: pedido original, avance, resultados de
subagentes, **fuentes consultadas (etiquetadas por origen)**, archivos
modificados, observaciones y métricas. `brief()` produce la vista compacta que se
inyecta en los prompts; `to_json()` produce el snapshot completo.

### `ToolContext` y `ToolRegistry`

`ToolContext` agrupa todo lo que una tool puede necesitar (config, política,
estado, tracer, LLM, RAG, memoria, función de aprobación). `ToolRegistry`
descubre los plugins, expone sus schemas al LLM, y centraliza la **validación de
políticas antes de cada ejecución**.

## Por qué sin frameworks

Toda la "orquestación" es código Python explícito: un `while` con una decisión
JSON del LLM y un `dict` de subagentes. Esto cumple la restricción de la consigna
y deja el control de errores, loops y contexto totalmente a la vista.
