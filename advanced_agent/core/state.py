"""Estado compartido de tarea (TaskState).

El agente principal y todos los subagentes comparten una única instancia de
TaskState. Registra el pedido original, el avance, los resultados de cada
subagente, las fuentes consultadas (diferenciadas por origen), los archivos
modificados y observaciones relevantes.

Diseñado para ser serializable a JSON en cualquier momento (snapshot/replay).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class SourceKind(str, Enum):
    """Origen de cada pieza de evidencia. La consigna exige diferenciar
    claramente entre estas categorías."""
    REPO = "repo"            # leído del repositorio
    MEMORY = "memory"        # memoria persistente del proyecto
    RAG = "rag"              # recuperado del índice RAG
    WEB = "web"              # búsqueda web
    INFERENCE = "inference"  # inferencia propia del modelo (sin fuente externa)


@dataclass
class Source:
    """Una fuente consultada, etiquetada por su origen."""
    kind: SourceKind
    ref: str                 # path, url, doc_id, etc.
    detail: str = ""         # fragmento o resumen de por qué es relevante
    score: float | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["kind"] = self.kind.value
        return d


@dataclass
class SubagentResult:
    """Resultado devuelto por un subagente al orquestador."""
    agent: str
    summary: str
    success: bool = True
    data: dict = field(default_factory=dict)
    sources: list[Source] = field(default_factory=list)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "summary": self.summary,
            "success": self.success,
            "data": self.data,
            "sources": [s.to_dict() for s in self.sources],
            "ts": self.ts,
        }


@dataclass
class TaskState:
    """Estado central compartido por todo el sistema."""
    request: str = ""                                  # pedido original del usuario
    status: str = "pending"                            # pending|running|done|blocked|failed
    progress: list[str] = field(default_factory=list)  # bitácora de avance
    subagent_results: list[SubagentResult] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)
    plan: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=lambda: {
        "llm_calls": 0, "tool_calls": 0, "tokens": 0,
        "cost_usd": 0.0, "subagent_calls": 0,
    })

    # -------- mutadores con bitácora --------
    def log(self, msg: str) -> None:
        self.progress.append(msg)

    def observe(self, msg: str) -> None:
        if msg not in self.observations:
            self.observations.append(msg)

    def add_source(self, source: Source) -> None:
        self.sources.append(source)

    def add_sources(self, sources: list[Source]) -> None:
        self.sources.extend(sources)

    def record_modified(self, path: str) -> None:
        if path not in self.modified_files:
            self.modified_files.append(path)

    def add_subagent_result(self, result: SubagentResult) -> None:
        self.subagent_results.append(result)
        self.add_sources(result.sources)

    def bump(self, metric: str, amount: float = 1) -> None:
        self.metrics[metric] = self.metrics.get(metric, 0) + amount

    # -------- vistas --------
    def sources_by_kind(self) -> dict[str, list[dict]]:
        """Devuelve las fuentes agrupadas por origen (repo/memory/rag/web/inference)."""
        out: dict[str, list[dict]] = {}
        for s in self.sources:
            out.setdefault(s.kind.value, []).append(s.to_dict())
        return out

    def to_dict(self) -> dict:
        return {
            "request": self.request,
            "status": self.status,
            "plan": self.plan,
            "progress": self.progress,
            "subagent_results": [r.to_dict() for r in self.subagent_results],
            "sources_by_kind": self.sources_by_kind(),
            "modified_files": self.modified_files,
            "observations": self.observations,
            "metrics": self.metrics,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def brief(self) -> str:
        """Resumen compacto del estado, apto para inyectar en prompts sin
        gastar todo el presupuesto de contexto."""
        parts = [f"PEDIDO: {self.request}", f"ESTADO: {self.status}"]
        if self.plan:
            parts.append("PLAN: " + " | ".join(self.plan[:6]))
        if self.progress:
            parts.append("AVANCE RECIENTE:\n- " + "\n- ".join(self.progress[-6:]))
        if self.modified_files:
            parts.append("ARCHIVOS MODIFICADOS: " + ", ".join(self.modified_files))
        if self.observations:
            parts.append("OBSERVACIONES:\n- " + "\n- ".join(self.observations[-5:]))
        return "\n".join(parts)
