"""DEMO 1 — Tarea que usa RAG y muestra las fuentes recuperadas.

Corre el sistema con un pedido que requiere conocimiento de FastAPI. El
Researcher consulta el RAG y devuelve los fragmentos con su fuente y score.
Al final imprime las fuentes diferenciadas por origen (rag/web/repo/memory).

Sin OPENAI_API_KEY usa un cerebro mock determinista (--mock implícito).
Con claves reales, llama a OpenAI/RAG de verdad.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from advanced_agent.system import AgentSystem
from mock_brains import make_rag_demo_brain   # noqa: E402  (tests/ en sys.path)

sys.path.insert(0, str(ROOT / "tests"))


def main():
    use_mock = not os.environ.get("OPENAI_API_KEY")
    handler = make_rag_demo_brain() if use_mock else None

    system = AgentSystem(config_path="agent.config.yaml", interactive=False,
                         mock=True if use_mock else None, mock_handler=handler,
                         run_name="demo-1-rag")

    print("=" * 70)
    print("DEMO 1 — RAG con fuentes recuperadas")
    print("=" * 70)
    if not system.rag.ready():
        print("\n[!] El índice RAG está vacío. Ejecutá primero:")
        print("    python -m advanced_agent.rag.ingest --mock\n")
        return

    request = ("¿Cómo se declara el request body y cómo se filtra la salida con "
               "response_model en FastAPI? Citá las fuentes de la documentación.")
    answer = system.run(request)

    print("\n--- RESPUESTA ---\n" + answer)
    print("\n--- FUENTES POR ORIGEN ---")
    for kind, items in system.state.sources_by_kind().items():
        print(f"\n[{kind}] ({len(items)})")
        for s in items[:5]:
            extra = f"  score={s['score']}" if s.get("score") is not None else ""
            print(f"  - {s['ref']}{extra}")
            if s.get("detail"):
                print(f"      «{s['detail'][:120].strip()}»")
    print(f"\nTrace: {system.tracer.trace_id} | log: {system.tracer.local_log_path}")


if __name__ == "__main__":
    main()
