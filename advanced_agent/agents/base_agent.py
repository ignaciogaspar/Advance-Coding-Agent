"""Clase base de los subagentes: un loop agéntico (razonar → tool → observar)
SIN frameworks de orquestación. Implementa, en el propio harness:

  - Bucle de tool-calling contra el LLMClient.
  - Detección de loops (acciones idénticas repetidas sin avanzar).
  - Manejo de falta de evidencia (el agente puede declarar BLOCKED y explicar
    qué intentó, qué falta y qué necesita).
  - Resumen de contexto para no enviar todo el historial en cada turno.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from ..tools.base import ToolRegistry
from ..core.state import SubagentResult, Source, SourceKind


@dataclass
class LoopDetector:
    """Detecta acciones idénticas repetidas. Si la misma (tool, args) o el
    mismo resultado de error aparece `window` veces seguidas, hay un loop."""
    window: int = 3
    _recent_actions: list[str] = field(default_factory=list)
    _recent_results: list[str] = field(default_factory=list)

    @staticmethod
    def _h(s: str) -> str:
        return hashlib.md5(s.encode()).hexdigest()[:10]

    def record(self, action: str, result: str) -> bool:
        """Devuelve True si se detecta un loop."""
        self._recent_actions.append(self._h(action))
        self._recent_results.append(self._h(result[:200]))
        self._recent_actions = self._recent_actions[-self.window:]
        self._recent_results = self._recent_results[-self.window:]
        if len(self._recent_actions) < self.window:
            return False
        same_action = len(set(self._recent_actions)) == 1
        same_result = len(set(self._recent_results)) == 1
        return same_action or same_result


class BaseAgent:
    """Subagente con un rol, un conjunto de tools habilitadas y un system prompt."""
    role: str = "agent"
    allowed_tools: list[str] = []

    def __init__(self, ctx, registry: ToolRegistry):
        self.ctx = ctx
        self.registry = registry
        limits = ctx.config.limits
        self.max_iterations = limits.get("max_iterations", 12)
        self.loop = LoopDetector(window=limits.get("loop_window", 3))

    # ------- a sobrescribir por cada subagente -------
    def system_prompt(self) -> str:
        return f"Eres el subagente {self.role}."

    def build_task_prompt(self, instruction: str) -> str:
        """Inyecta SÓLO el brief del estado (no el repo/historial completo)."""
        return (f"INSTRUCCIÓN PARA EL SUBAGENTE {self.role.upper()}:\n{instruction}\n\n"
                f"--- CONTEXTO (estado compartido) ---\n{self.ctx.state.brief()}\n\n"
                "Cuando termines, respondé con un resumen claro y conciso de lo que "
                "hiciste o encontraste. Si NO tenés evidencia suficiente, decí "
                "explícitamente 'FALTA EVIDENCIA' y explicá: qué intentaste, qué "
                "información falta y qué necesitás para continuar.")

    # ------- el loop agéntico -------
    def run(self, instruction: str) -> SubagentResult:
        ctx = self.ctx
        ctx.state.bump("subagent_calls")
        messages = [
            {"role": "system", "content": self.system_prompt()},
            {"role": "user", "content": self.build_task_prompt(instruction)},
        ]
        tools = self.registry.schemas(only=self.allowed_tools or None)

        with ctx.tracer.span(f"subagent:{self.role}", kind="subagent",
                             instruction=instruction[:200]) as h:
            for i in range(1, self.max_iterations + 1):
                ctx.state.bump("llm_calls")
                resp = ctx.llm.chat(messages, tools=tools)
                content = resp.get("content")
                tool_calls = resp.get("tool_calls", [])

                if not tool_calls:
                    # Respuesta final del subagente.
                    final = content or ""
                    blocked = "FALTA EVIDENCIA" in final.upper()
                    h["output"] = final[:300]
                    return self._result(final, success=not blocked, blocked=blocked)

                # Registrar el assistant con sus tool_calls (historial portable).
                messages.append({
                    "role": "assistant", "content": content,
                    "tool_calls": [{"id": tc["id"], "type": "function",
                                    "function": {"name": tc["name"],
                                                 "arguments": json.dumps(tc["arguments"])}}
                                   for tc in tool_calls],
                })

                for tc in tool_calls:
                    name, args = tc["name"], tc["arguments"]
                    result = self.registry.execute(name, args)

                    # --- detección de loops ---
                    action_sig = f"{name}:{json.dumps(args, sort_keys=True)}"
                    if self.loop.record(action_sig, result):
                        ctx.state.observe(
                            f"[{self.role}] LOOP detectado: repitió «{name}» sin avanzar. "
                            "Cambiando de estrategia / deteniéndose.")
                        messages.append({"role": "tool", "tool_call_id": tc["id"],
                                         "name": name, "content": result})
                        messages.append({"role": "user", "content":
                            "DETECCIÓN DE LOOP: estás repitiendo la misma acción sin "
                            "obtener información nueva. Cambiá de estrategia o, si no es "
                            "posible, respondé 'FALTA EVIDENCIA' explicando el bloqueo."})
                        # Forzar una iteración de replanteo y luego cortar.
                        ctx.llm and ctx.state.bump("llm_calls")
                        replan = ctx.llm.chat(messages, tools=tools)
                        final = replan.get("content") or (
                            f"[{self.role}] Detenido por loop sin avance.")
                        blocked = "FALTA EVIDENCIA" in final.upper() or not replan.get("content")
                        h["output"] = final[:300]
                        return self._result(final, success=not blocked, blocked=True)

                    messages.append({"role": "tool", "tool_call_id": tc["id"],
                                     "name": name, "content": result})

            # Se acabaron las iteraciones sin respuesta final.
            ctx.state.observe(f"[{self.role}] alcanzó el límite de iteraciones.")
            return self._result(
                f"[{self.role}] Límite de iteraciones alcanzado sin conclusión.",
                success=False, blocked=True)

    def _result(self, summary: str, success: bool, blocked: bool) -> SubagentResult:
        if blocked:
            self.ctx.state.observe(f"[{self.role}] BLOQUEADO: {summary[:120]}")
        return SubagentResult(agent=self.role, summary=summary, success=success,
                              data={"blocked": blocked})
