"""Tools de memoria persistente del proyecto. Permiten a los agentes leer y
escribir hechos persistentes (arquitectura, archivos clave, dependencias,
comandos útiles, convenciones, decisiones, bugs, resúmenes de sesión).
"""
from __future__ import annotations

from ..base import Tool, ToolContext
from ...core.state import Source, SourceKind


class MemoryReadTool(Tool):
    name = "memory_read"
    description = ("Lee la memoria persistente del proyecto. Sin sección, "
                   "devuelve un resumen de todas las secciones.")
    permission = "none"
    parameters = {
        "type": "object",
        "properties": {"section": {"type": "string",
                       "description": "architecture|key_files|dependencies|commands|"
                                      "conventions|decisions|bugs|session_summaries"}},
    }

    def run(self, ctx: ToolContext, section: str | None = None) -> str:
        if ctx.memory is None:
            return "Memoria no disponible."
        if section:
            items = ctx.memory.get(section)
            if not items:
                return f"Memoria['{section}']: (vacío)"
            ctx.state.add_source(Source(SourceKind.MEMORY, section,
                                        "memoria persistente del proyecto"))
            return f"Memoria['{section}']:\n- " + "\n- ".join(str(i) for i in items)
        ctx.state.add_source(Source(SourceKind.MEMORY, "all", "resumen de memoria"))
        return ctx.memory.summary()


class MemoryWriteTool(Tool):
    name = "memory_write"
    description = ("Agrega un hecho persistente a una sección de la memoria del "
                   "proyecto para reutilizarlo en sesiones futuras.")
    permission = "none"
    parameters = {
        "type": "object",
        "properties": {
            "section": {"type": "string",
                        "description": "architecture|key_files|dependencies|commands|"
                                       "conventions|decisions|bugs|session_summaries"},
            "content": {"type": "string", "description": "Hecho a guardar."},
        },
        "required": ["section", "content"],
    }

    def run(self, ctx: ToolContext, section: str, content: str) -> str:
        if ctx.memory is None:
            return "Memoria no disponible."
        ok = ctx.memory.add(section, content)
        if not ok:
            return f"Sección inválida '{section}'. Válidas: {', '.join(ctx.memory.SECTIONS)}"
        return f"Memoria actualizada: [{section}] += «{content[:80]}»"
