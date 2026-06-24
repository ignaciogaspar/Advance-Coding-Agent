"""Agente principal (orquestador).

Recibe la tarea del usuario, mantiene el estado general y coordina a los
subagentes. Implementa la coordinación SIN frameworks: pide al LLM un plan de
delegación (qué subagente y con qué instrucción), ejecuta cada paso, integra el
resultado en el estado compartido, y decide el siguiente paso, con tope de
delegaciones y manejo de bloqueos.
"""
from __future__ import annotations

import json

from ..core.state import SourceKind
from .subagents import SUBAGENTS


PLANNER_SYSTEM = (
    "Eres el AGENTE PRINCIPAL de un sistema multi-agente de código. Coordinás 5 "
    "subagentes especializados:\n"
    "- explorer: entiende el repo (arquitectura, deps, archivos clave). Sólo lectura.\n"
    "- researcher: busca en RAG (primero) y web (fallback). Devuelve fuentes.\n"
    "- implementer: hace cambios de código.\n"
    "- tester: corre tests / validaciones.\n"
    "- reviewer: valida que el resultado responda al pedido.\n\n"
    "Tu trabajo: descomponer el pedido en pasos y, en cada turno, decidir el "
    "SIGUIENTE paso. Respondé SIEMPRE en JSON válido con esta forma:\n"
    '{\"action\": \"delegate\"|\"finish\"|\"need_user\", '
    '\"agent\": \"<subagente>\", \"instruction\": \"<qué debe hacer>\", '
    '\"final\": \"<respuesta final o pregunta al usuario>\"}\n'
    "Reglas:\n"
    "- Empezá normalmente por explorer para entender el repo.\n"
    "- Usá researcher cuando necesites conocimiento de la tecnología.\n"
    "- Para cambios de código: implementer y luego tester y reviewer.\n"
    "- Si un subagente reporta FALTA EVIDENCIA o queda BLOQUEADO, no insistas con "
    "lo mismo: cambiá de estrategia, o usá action 'need_user' para pedir ayuda.\n"
    "- Cuando la tarea esté completa y revisada, usá action 'finish' con 'final'."
)


class Orchestrator:
    def __init__(self, ctx, registry):
        self.ctx = ctx
        self.registry = registry
        self.max_subagent_calls = ctx.config.limits.get("max_subagent_calls", 8)
        self._delegation_history: list[str] = []

    # ---------------- manejo de contexto largo ----------------
    def _maybe_summarize(self) -> None:
        """Evita enviar todo el historial: si el estado creció mucho, resume el
        avance previo conservando decisiones importantes."""
        budget = self.ctx.config.limits.get("context_token_budget", 8000)
        approx_tokens = len(self.ctx.state.to_json()) // 4
        if approx_tokens <= budget:
            return
        with self.ctx.tracer.span("context-summarize", kind="summary"):
            self.ctx.state.bump("llm_calls")
            prompt = [
                {"role": "system", "content":
                 "Resumí el avance del proyecto conservando decisiones y resultados "
                 "importantes en 6-10 viñetas. Descartá detalle redundante."},
                {"role": "user", "content": self.ctx.state.to_json()},
            ]
            resp = self.ctx.llm.chat(prompt)
            summary = resp.get("content") or ""
            # Compactar el progreso: dejamos sólo el resumen.
            self.ctx.state.progress = [f"[resumen de contexto] {summary}"]
            self.ctx.state.observe("Historial resumido para respetar el presupuesto de contexto.")

    # ---------------- bucle de coordinación ----------------
    def run(self, request: str) -> str:
        ctx = self.ctx
        ctx.state.request = request
        ctx.state.status = "running"

        # Sembrar memoria de sesión al inicio (si hay memoria de sesiones previas).
        if ctx.memory and not ctx.memory.is_empty():
            ctx.state.observe("Se cargó memoria persistente de sesiones anteriores.")

        messages = [
            {"role": "system", "content": PLANNER_SYSTEM},
            {"role": "user", "content":
             f"PEDIDO DEL USUARIO:\n{request}\n\n"
             f"MEMORIA DEL PROYECTO:\n{ctx.memory.summary() if ctx.memory else '(sin memoria)'}\n\n"
             "Decidí el primer paso (JSON)."},
        ]

        final_answer = ""
        for step in range(1, self.max_subagent_calls + 1):
            self._maybe_summarize()
            ctx.state.bump("llm_calls")
            with ctx.tracer.span(f"orchestrator-decide-{step}", kind="plan"):
                resp = ctx.llm.chat(messages)
            decision = self._parse_decision(resp.get("content"))
            ctx.state.log(f"[orquestador] paso {step}: {decision.get('action')} "
                          f"→ {decision.get('agent', '-')}")

            action = decision.get("action")

            if action == "finish":
                final_answer = decision.get("final") or "Tarea completada."
                ctx.state.status = "done"
                break

            if action == "need_user":
                final_answer = decision.get("final") or (
                    "Necesito más información para continuar.")
                ctx.state.status = "blocked"
                ctx.state.observe("El orquestador pidió ayuda al usuario (falta evidencia/ambigüedad).")
                break

            # action == "delegate"
            agent_name = decision.get("agent")
            instruction = decision.get("instruction", request)
            if agent_name not in SUBAGENTS:
                messages.append({"role": "user", "content":
                    f"Subagente inválido '{agent_name}'. Elegí uno de: "
                    f"{', '.join(SUBAGENTS)}."})
                continue

            # Anti-loop a nivel orquestador: misma delegación repetida.
            sig = f"{agent_name}:{instruction}"
            if self._delegation_history[-2:] == [sig, sig]:
                ctx.state.observe(
                    "Orquestador: delegación repetida sin avance → pide ayuda al usuario.")
                final_answer = (
                    "Me quedé sin estrategias nuevas: estoy repitiendo la misma "
                    f"delegación a '{agent_name}' sin progresar. Necesito que aclares "
                    "el objetivo o relajes alguna restricción.")
                ctx.state.status = "blocked"
                break
            self._delegation_history.append(sig)

            # Ejecutar el subagente.
            subagent = SUBAGENTS[agent_name](ctx, self.registry)
            result = subagent.run(instruction)
            ctx.state.add_subagent_result(result)

            messages.append({"role": "assistant", "content": json.dumps(decision)})
            messages.append({"role": "user", "content":
                f"RESULTADO de {agent_name} (success={result.success}, "
                f"blocked={result.data.get('blocked')}):\n{result.summary}\n\n"
                f"ESTADO ACTUAL:\n{ctx.state.brief()}\n\n"
                "Decidí el siguiente paso (JSON)."})
        else:
            final_answer = ("Alcancé el tope de delegaciones sin cerrar la tarea. "
                            "Revisá el estado para ver el avance parcial.")
            ctx.state.status = "blocked"

        # Persistir resumen de sesión en memoria.
        if ctx.memory:
            ctx.memory.record_session_summary(request, final_answer)
        return final_answer

    # ---------------- helpers ----------------
    @staticmethod
    def _parse_decision(content: str | None) -> dict:
        if not content:
            return {"action": "need_user", "final": "No recibí una decisión del modelo."}
        text = content.strip()
        # Extraer el primer bloque JSON aunque venga con texto alrededor.
        if "```" in text:
            text = text.split("```")[1].replace("json", "", 1).strip()
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end + 1])
            except Exception:  # noqa: BLE001
                pass
        return {"action": "need_user",
                "final": f"No pude parsear la decisión: {content[:200]}"}
