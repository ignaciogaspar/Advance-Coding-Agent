"""Observabilidad — integración con Langfuse + log local degradado.

Registra la información mínima exigida por la consigna: prompts, modelo,
llamadas al LLM, tools invocadas, documentos recuperados, búsquedas web,
iteraciones, errores, latencia, tokens, costo estimado y resultado final.

Si Langfuse no está instalado o faltan las claves, el tracer NO falla: cae a
un log local en JSONL (data/traces.jsonl) para que el sistema siga siendo
observable incluso offline.
"""
from __future__ import annotations

import json
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

# Precio aproximado por 1K tokens (USD) — sólo para estimar costo.
PRICE_PER_1K = {
    "gpt-4o-mini": {"in": 0.00015, "out": 0.0006},
    "gpt-4o": {"in": 0.0025, "out": 0.01},
    "gpt-5-nano": {"in": 0.00005, "out": 0.0004},
    "text-embedding-3-small": {"in": 0.00002, "out": 0.0},
}


def estimate_cost(model: str, in_tokens: int, out_tokens: int = 0) -> float:
    p = PRICE_PER_1K.get(model, {"in": 0.0, "out": 0.0})
    return (in_tokens / 1000) * p["in"] + (out_tokens / 1000) * p["out"]


class Tracer:
    """Fachada de tracing. Una instancia por ejecución del agente.

    Crea una traza raíz y permite anidar "spans" (observaciones) para cada
    paso: llamada LLM, tool call, retrieval RAG, búsqueda web, etc.
    """

    def __init__(self, config: dict | None = None, run_name: str = "agent-run"):
        config = config or {}
        self.enabled = config.get("enabled", True)
        self.run_name = run_name
        self.trace_id = str(uuid.uuid4())
        self.local_log_path = Path(config.get("local_log", "./data/traces.jsonl"))
        self.local_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lf = None
        self._lf_trace = None
        self.totals = {"tokens": 0, "cost_usd": 0.0, "llm_calls": 0,
                       "tool_calls": 0, "errors": 0}

        if self.enabled and config.get("provider", "langfuse") == "langfuse":
            self._init_langfuse()

    def _init_langfuse(self) -> None:
        try:
            from langfuse import Langfuse  # type: ignore
            import os
            if not (os.environ.get("LANGFUSE_PUBLIC_KEY")
                    and os.environ.get("LANGFUSE_SECRET_KEY")):
                self._log_local("warn", {"msg": "Langfuse keys missing; local-only tracing"})
                return
            self._lf = Langfuse()
            self._lf_trace = self._lf.trace(name=self.run_name, id=self.trace_id)
        except Exception as e:  # noqa: BLE001
            self._log_local("warn", {"msg": f"Langfuse no disponible: {e}; local-only"})

    # ---------- logging local ----------
    def _log_local(self, event: str, payload: dict) -> None:
        rec = {"ts": time.time(), "trace_id": self.trace_id, "event": event, **payload}
        with open(self.local_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")

    # ---------- spans de alto nivel ----------
    @contextmanager
    def span(self, name: str, kind: str = "step", **meta):
        """Context manager que mide latencia y registra entrada/salida."""
        start = time.time()
        lf_span = None
        if self._lf_trace is not None:
            try:
                lf_span = self._lf_trace.span(name=name, metadata={"kind": kind, **meta})
            except Exception:  # noqa: BLE001
                lf_span = None
        holder: dict[str, Any] = {"output": None, "error": None}
        try:
            yield holder
        except Exception as e:  # noqa: BLE001
            holder["error"] = str(e)
            self.totals["errors"] += 1
            raise
        finally:
            latency = round(time.time() - start, 4)
            self._log_local(kind, {"name": name, "latency_s": latency,
                                   "meta": meta, "output": holder.get("output"),
                                   "error": holder.get("error")})
            if lf_span is not None:
                try:
                    lf_span.end(output=holder.get("output"),
                                metadata={"latency_s": latency,
                                          "error": holder.get("error")})
                except Exception:  # noqa: BLE001
                    pass

    def log_llm(self, model: str, prompt_preview: str, in_tokens: int,
                out_tokens: int, latency_s: float, output_preview: str = "") -> None:
        cost = estimate_cost(model, in_tokens, out_tokens)
        self.totals["tokens"] += in_tokens + out_tokens
        self.totals["cost_usd"] += cost
        self.totals["llm_calls"] += 1
        self._log_local("llm", {
            "model": model, "prompt_preview": prompt_preview[:400],
            "in_tokens": in_tokens, "out_tokens": out_tokens,
            "latency_s": latency_s, "cost_usd": round(cost, 6),
            "output_preview": output_preview[:400],
        })
        if self._lf_trace is not None:
            try:
                self._lf_trace.generation(
                    name="llm-call", model=model,
                    input=prompt_preview[:1000], output=output_preview[:1000],
                    usage={"input": in_tokens, "output": out_tokens},
                    metadata={"latency_s": latency_s, "cost_usd": cost},
                )
            except Exception:  # noqa: BLE001
                pass

    def log_tool(self, name: str, args: dict, result_preview: str,
                 ok: bool = True) -> None:
        self.totals["tool_calls"] += 1
        self._log_local("tool", {"tool": name, "args": args,
                                 "result_preview": str(result_preview)[:400], "ok": ok})

    def log_retrieval(self, query: str, docs: list[dict]) -> None:
        self._log_local("retrieval", {"query": query,
                                      "docs": [{"id": d.get("id"), "score": d.get("score")}
                                               for d in docs]})

    def log_web(self, query: str, results: list[dict]) -> None:
        self._log_local("web_search", {"query": query, "n": len(results)})

    def finish(self, status: str, final_output: str) -> None:
        self._log_local("final", {"status": status,
                                  "final_preview": final_output[:600],
                                  "totals": self.totals})
        if self._lf_trace is not None:
            try:
                self._lf_trace.update(output=final_output[:2000],
                                      metadata={"status": status, **self.totals})
                if self._lf:
                    self._lf.flush()
            except Exception:  # noqa: BLE001
                pass
