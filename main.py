#!/usr/bin/env python3
"""CLI del Coding Agent Avanzado.

Uso:
    python main.py "Analizá la arquitectura de la API y resumí los endpoints"
    python main.py                 # modo interactivo (REPL)
    python main.py --tools         # lista las tools descubiertas
    python main.py --state         # imprime el estado final en JSON

Variables de entorno (ver .env.example):
    OPENAI_API_KEY, TAVILY_API_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY
"""
from __future__ import annotations

import argparse
import os
import sys

# Carga simple de .env (sin dependencia extra).
def _load_dotenv(path: str = ".env") -> None:
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main() -> None:
    _load_dotenv()
    ap = argparse.ArgumentParser(description="Coding Agent Avanzado (multi-agente).")
    ap.add_argument("request", nargs="*", help="Pedido para el agente.")
    ap.add_argument("--config", default="agent.config.yaml")
    ap.add_argument("--tools", action="store_true", help="Lista las tools y sale.")
    ap.add_argument("--state", action="store_true", help="Imprime el estado final JSON.")
    ap.add_argument("--mock", action="store_true",
                    help="Modo mock (sin red ni claves) para smoke tests.")
    ap.add_argument("--non-interactive", action="store_true",
                    help="No pedir aprobaciones por consola (auto-deny).")
    args = ap.parse_args()

    from advanced_agent.system import AgentSystem

    system = AgentSystem(
        config_path=args.config,
        interactive=not args.non_interactive,
        mock=True if args.mock else None,
        run_name="cli-run",
    )

    if args.tools:
        print("Tools descubiertas (plugins):")
        for t in system.tools():
            tool = system.registry.get(t)
            print(f"  - {t} [{tool.permission}]: {tool.description}")
        return

    if args.request:
        request = " ".join(args.request)
        _run_once(system, request, show_state=args.state)
        return

    # REPL interactivo.
    print("🤖 Coding Agent Avanzado. Escribí tu pedido (o 'salir').")
    print(f"   Workspace: {system.config.workspace}")
    print(f"   Tools: {', '.join(system.tools())}\n")
    while True:
        try:
            req = input("👤 Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if req.lower() in {"salir", "exit", "quit"}:
            break
        if not req:
            continue
        _run_once(system, req, show_state=args.state)
        # Estado nuevo por pedido (memoria persiste en disco).
        from advanced_agent.system import AgentSystem as _AS
        system = _AS(config_path=args.config,
                     interactive=not args.non_interactive,
                     mock=True if args.mock else None, run_name="cli-run")


def _run_once(system, request: str, show_state: bool = False) -> None:
    print(f"\n[trace_id={system.tracer.trace_id}]")
    answer = system.run(request)
    print("\n🤖 Respuesta final:\n" + answer)
    m = system.state.metrics
    print(f"\n📊 Métricas: llm_calls={m['llm_calls']} tool_calls={m['tool_calls']} "
          f"subagentes={m['subagent_calls']} tokens={m['tokens']} "
          f"costo≈${m['cost_usd']} errores={m.get('errors', 0)}")
    print("📚 Fuentes por origen: " +
          ", ".join(f"{k}={len(v)}" for k, v in system.state.sources_by_kind().items())
          or "(ninguna)")
    if show_state:
        print("\n--- ESTADO FINAL ---\n" + system.state.to_json())


if __name__ == "__main__":
    main()
