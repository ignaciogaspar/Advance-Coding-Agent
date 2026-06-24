"""Tool de búsqueda web — preservada del harness original (Tavily).

Según la política de búsqueda de la consigna, el web_search es el fallback
cuando el RAG no tiene evidencia suficiente. Prioriza documentación oficial.
"""
from __future__ import annotations

import os

import requests

from ..base import Tool, ToolContext
from ...core.state import Source, SourceKind


class WebSearchTool(Tool):
    name = "web_search"
    description = ("Busca en la web (Tavily). Úsese SÓLO si el RAG no aportó "
                   "evidencia suficiente. Prioriza fuentes oficiales.")
    permission = "none"
    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "Consulta de búsqueda."}},
        "required": ["query"],
    }

    def run(self, ctx: ToolContext, query: str) -> str:
        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            return "Error: no hay TAVILY_API_KEY configurada."
        try:
            resp = requests.post(
                "https://api.tavily.com/search",
                json={"api_key": api_key, "query": query, "max_results": 3,
                      "include_answer": True},
                timeout=20,
            )
            data = resp.json()
        except Exception as e:  # noqa: BLE001
            return f"Error en búsqueda web: {e}"

        results = data.get("results", [])
        ctx.tracer.log_web(query, results)
        lines = []
        if data.get("answer"):
            lines.append(f"RESPUESTA: {data['answer']}")
        for r in results:
            url = r.get("url", "")
            title = r.get("title", "")
            snippet = (r.get("content") or "").strip().replace("\n", " ")[:280]
            lines.append(f"- {title} ({url})\n  {snippet}")
            ctx.state.add_source(Source(SourceKind.WEB, url, title))
        return "\n".join(lines) if lines else "Sin resultados."
