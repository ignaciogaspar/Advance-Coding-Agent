"""Ensamblado del sistema: construye el contexto compartido (config, política,
estado, tracer, LLM, RAG, memoria), registra las tools y devuelve el orquestador
listo para correr. Punto único de cableado.
"""
from __future__ import annotations

import os

from .core.config import load_config
from .core.llm import LLMClient
from .core.observability import Tracer
from .core.state import TaskState
from .core.config import PolicyEngine
from .memory.project_memory import ProjectMemory
from .rag.index import RagIndex
from .tools.base import ToolContext, ToolRegistry
from .agents.orchestrator import Orchestrator


def _default_approver(interactive: bool):
    """Devuelve una función de aprobación de comandos."""
    def approve(command: str) -> bool:
        if not interactive:
            # Modo no interactivo: por seguridad, denegar lo que requiere aprobación.
            print(f"[auto-deny] comando que requiere aprobación: {command}")
            return False
        ans = input(f"⚠️  El agente quiere ejecutar (requiere aprobación): "
                    f"`{command}`\n   ¿Autorizar? (s/n): ")
        return ans.strip().lower() == "s"
    return approve


class AgentSystem:
    def __init__(self, config_path: str = "agent.config.yaml",
                 interactive: bool = True, mock: bool | None = None,
                 mock_handler=None, run_name: str = "agent-run"):
        self.config = load_config(config_path)
        self.tracer = Tracer(self.config.observability, run_name=run_name)
        self.state = TaskState()
        self.policy = PolicyEngine(self.config)
        self.llm = LLMClient(self.config.chat_model, self.config.embed_model,
                             self.tracer, mock=mock, mock_handler=mock_handler)
        self.memory = ProjectMemory(self.config.memory_path)
        rag_cfg = self.config.rag
        self.rag = RagIndex(
            index_path=self.config.resolve(rag_cfg.get("index_path", "./data/rag_index.json")),
            llm=self.llm,
            chunk_size=rag_cfg.get("chunk_size", 800),
            overlap=rag_cfg.get("chunk_overlap", 150),
        )
        self.ctx = ToolContext(
            config=self.config, policy=self.policy, state=self.state,
            tracer=self.tracer, llm=self.llm, rag=self.rag, memory=self.memory,
            approve=_default_approver(interactive),
        )
        self.registry = ToolRegistry(self.ctx)
        self.orchestrator = Orchestrator(self.ctx, self.registry)

    def new_turn(self, run_name: str = "agent-run") -> None:
        """Arranca un nuevo turno de conversación SIN perder el TaskState.

        Antes, el REPL creaba un AgentSystem nuevo en cada pedido, lo que
        recreaba `TaskState` desde cero (`self.state = TaskState()` en
        `__init__`) y borraba todo lo que el agente había leído/hecho en
        turnos previos de la MISMA sesión (progress, sources,
        modified_files, subagent_results). Eso hacía que pedidos de
        continuación ("continua", "documenta los cambios") llegaran sin
        contexto real.

        Este método crea un Tracer nuevo (para tener una traza por
        ejecución, como pide la consigna) y un Orchestrator nuevo (resetea
        el anti-loop de delegaciones repetidas), pero conserva `self.state`
        y `self.memory` intactos. La memoria persistente en disco
        (ProjectMemory) sigue siendo la que sobrevive entre ejecuciones
        distintas del proceso (`python3 main.py` nuevo).
        """
        self.tracer = Tracer(self.config.observability, run_name=run_name)
        self.ctx.tracer = self.tracer
        self.orchestrator = Orchestrator(self.ctx, self.registry)

    def run(self, request: str) -> str:
        try:
            answer = self.orchestrator.run(request)
        finally:
            self.tracer.finish(self.state.status, self.state.brief())
        self.state.metrics.update({
            "tokens": self.tracer.totals["tokens"],
            "cost_usd": round(self.tracer.totals["cost_usd"], 6),
            "llm_calls": self.tracer.totals["llm_calls"],
            "tool_calls": self.tracer.totals["tool_calls"],
            "errors": self.tracer.totals["errors"],
        })
        return answer

    def tools(self) -> list[str]:
        return self.registry.names()