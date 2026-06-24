"""DEMO 4 — Ejecución registrada en la herramienta de observabilidad.

Corre una tarea y muestra que TODA la traza quedó registrada: con
LANGFUSE_PUBLIC_KEY/SECRET_KEY se envía a Langfuse (cloud o self-host); sin
claves, cae al log local JSONL (data/traces.jsonl), que también es una traza
completa y auditable.

Imprime un resumen de la traza con la información mínima exigida: prompts,
modelo, llamadas LLM, tools, retrieval, iteraciones, latencia, tokens, costo.
"""
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
os.chdir(ROOT)

from advanced_agent.system import AgentSystem
from mock_brains import make_rag_demo_brain   # noqa: E402


def main():
    use_mock = not os.environ.get("OPENAI_API_KEY")
    has_langfuse = bool(os.environ.get("LANGFUSE_PUBLIC_KEY")
                        and os.environ.get("LANGFUSE_SECRET_KEY"))

    print("=" * 70)
    print("DEMO 4 — Observabilidad (Langfuse + log local)")
    print("=" * 70)
    print(f"Langfuse activo: {has_langfuse}  |  modo mock: {use_mock}")

    system = AgentSystem("agent.config.yaml", interactive=False,
                         mock=True if use_mock else None,
                         mock_handler=make_rag_demo_brain() if use_mock else None,
                         run_name="demo-4-observability")
    trace_id = system.tracer.trace_id
    log_path = Path(system.tracer.local_log_path)

    system.run("Resumí cómo se declara un request body en FastAPI (con fuentes RAG).")

    # Leer del log local las entradas de ESTA traza.
    events = []
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("trace_id") == trace_id:
                events.append(rec)

    kinds = Counter(e["event"] for e in events)
    print(f"\nTrace ID: {trace_id}")
    print(f"Eventos registrados ({len(events)}): {dict(kinds)}")

    print("\n--- Información mínima registrada ---")
    print(f"  modelo(s):        {sorted({e.get('model') for e in events if e.get('model')})}")
    print(f"  llamadas LLM:     {system.tracer.totals['llm_calls']}")
    print(f"  tools invocadas:  {system.tracer.totals['tool_calls']}")
    print(f"  retrievals RAG:   {kinds.get('retrieval', 0)}")
    print(f"  búsquedas web:    {kinds.get('web_search', 0)}")
    print(f"  errores:          {system.tracer.totals['errors']}")
    print(f"  tokens (aprox):   {system.tracer.totals['tokens']}")
    print(f"  costo estimado:   ${round(system.tracer.totals['cost_usd'], 6)}")
    lat = [e.get("latency_s") for e in events if e.get("latency_s")]
    if lat:
        print(f"  latencia total:   {round(sum(lat), 3)}s  (max paso {max(lat)}s)")

    if has_langfuse:
        print("\n[OK] La traza también se envió a Langfuse. Abrí el dashboard para "
              "ver el árbol de spans (orquestador → subagentes → tools → LLM).")
    else:
        print(f"\n[i] Sin claves Langfuse: la traza completa quedó en {log_path}")
        print("    Configurá LANGFUSE_* en .env para ver el dashboard y sacar capturas.")


if __name__ == "__main__":
    main()
