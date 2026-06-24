"""Interfaz común de tools + registro con descubrimiento automático (plugins).

Cada tool implementa una interfaz uniforme:
  - name           : identificador
  - description    : qué hace (lo ve el LLM)
  - parameters     : JSON schema de argumentos
  - permission     : "read" | "write" | "command" | "none" (qué política aplica)
  - run(ctx, **kw) : ejecución

El ToolRegistry descubre automáticamente todas las subclases de Tool ubicadas
en el paquete `advanced_agent.tools.plugins`, de modo que agregar una tool nueva
es soltar un archivo en esa carpeta — sin tocar el núcleo del harness.
"""
from __future__ import annotations

import importlib
import pkgutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolContext:
    """Todo lo que una tool puede necesitar para ejecutarse."""
    config: Any                 # AgentConfig
    policy: Any                 # PolicyEngine
    state: Any                  # TaskState
    tracer: Any                 # Tracer
    llm: Any = None             # LLMClient (para tools que razonan, p.ej. rag)
    rag: Any = None             # RagIndex
    memory: Any = None          # ProjectMemory
    approve: Any = None         # callable(command:str)->bool para aprobaciones


class Tool(ABC):
    name: str = ""
    description: str = ""
    parameters: dict = {"type": "object", "properties": {}}
    permission: str = "none"    # read | write | command | none

    @abstractmethod
    def run(self, ctx: ToolContext, **kwargs) -> str:
        ...

    # Schema en el formato que espera la API de OpenAI.
    @classmethod
    def openai_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": cls.name,
                "description": cls.description,
                "parameters": cls.parameters,
            },
        }


class ToolRegistry:
    """Descubre, habilita y ejecuta tools aplicando las políticas."""

    def __init__(self, ctx: ToolContext, enabled: list[str] | None = None):
        self.ctx = ctx
        self._tools: dict[str, Tool] = {}
        self.discover(enabled)

    def discover(self, enabled: list[str] | None = None) -> None:
        """Importa todos los módulos de tools.plugins y registra sus Tools."""
        from . import plugins
        for _, modname, _ in pkgutil.iter_modules(plugins.__path__):
            importlib.import_module(f"{plugins.__name__}.{modname}")
        for sub in _all_subclasses(Tool):
            if not getattr(sub, "name", ""):
                continue
            if enabled is not None and sub.name not in enabled:
                continue
            self._tools[sub.name] = sub()

    def names(self) -> list[str]:
        return sorted(self._tools)

    def schemas(self, only: list[str] | None = None) -> list[dict]:
        items = self._tools.values()
        if only is not None:
            items = [t for t in items if t.name in only]
        return [type(t).openai_schema() for t in items]

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def execute(self, name: str, args: dict) -> str:
        """Ejecuta una tool VALIDANDO la política correspondiente primero.

        Esta es la única puerta de ejecución: aquí se centraliza la
        verificación de permisos exigida por la consigna ("la configuración
        debe validarse antes de ejecutar cada tool call").
        """
        from ..core.config import PermissionDenied, ApprovalRequired

        tool = self._tools.get(name)
        if tool is None:
            return f"Error: tool desconocida '{name}'."

        ctx = self.ctx
        try:
            self._check_policy(tool, args)
        except PermissionDenied as e:
            ctx.state.observe(f"Política DENEGÓ {name}({args}): {e}")
            ctx.tracer.log_tool(name, args, f"DENIED: {e}", ok=False)
            return f"DENEGADO por política: {e}"
        except ApprovalRequired as e:
            approved = bool(ctx.approve and ctx.approve(e.command))
            if not approved:
                ctx.tracer.log_tool(name, args, "APPROVAL DENIED", ok=False)
                return f"Operación NO autorizada por el usuario: {e.command}"

        # Ejecutar dentro de un span para medir latencia.
        with ctx.tracer.span(f"tool:{name}", kind="tool", args=args) as h:
            try:
                result = tool.run(ctx, **args)
                ctx.state.bump("tool_calls")
                ctx.tracer.log_tool(name, args, result, ok=True)
                h["output"] = str(result)[:500]
                return result
            except PermissionDenied as e:
                ctx.tracer.log_tool(name, args, f"DENIED: {e}", ok=False)
                return f"DENEGADO por política: {e}"
            except Exception as e:  # noqa: BLE001
                ctx.tracer.log_tool(name, args, f"ERROR: {e}", ok=False)
                return f"Error ejecutando {name}: {e}"

    def _check_policy(self, tool: Tool, args: dict) -> None:
        """Aplica la política según el tipo de permiso de la tool."""
        from ..core.config import PermissionDenied, ApprovalRequired
        policy = self.ctx.policy
        if tool.permission == "read":
            path = args.get("path") or args.get("filepath") or args.get("directory") or "."
            d = policy.check_read(path)
            if not d.allowed:
                raise PermissionDenied(d.reason, kind="read", target=path)
        elif tool.permission == "write":
            path = args.get("path") or args.get("filepath", "")
            d = policy.check_write(path)
            if not d.allowed:
                raise PermissionDenied(d.reason, kind="write", target=path)
        elif tool.permission == "command":
            cmd = args.get("command", "")
            d = policy.check_command(cmd)
            if not d.allowed:
                raise PermissionDenied(d.reason, kind="command", target=cmd)
            if d.needs_approval:
                raise ApprovalRequired(d.reason, command=cmd)


def _all_subclasses(cls) -> set:
    subs = set(cls.__subclasses__())
    for s in list(subs):
        subs |= _all_subclasses(s)
    return subs
