"""Tool de recuperación RAG. Consulta el índice vectorial y devuelve los
fragmentos relevantes con su fuente y score, etiquetados como origen RAG.

Esta tool materializa la regla "consultar primero el RAG": el Researcher la
usa antes de recurrir a la web.
"""
from __future__ import annotations

from ..base import Tool, ToolContext
from ...core.state import Source, SourceKind


class RagSearchTool(Tool):
    name = "rag_search"
    description = ("Recupera fragmentos de la documentación técnica indexada "
                   "(RAG). Devuelve documentos, scores y fragmentos citados.")
    permission = "none"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Pregunta o tema a buscar."},
            "top_k": {"type": "integer", "description": "Cantidad de fragmentos (default config)."},
        },
        "required": ["query"],
    }

    def run(self, ctx: ToolContext, query: str, top_k: int | None = None) -> str:
        if ctx.rag is None or not ctx.rag.ready():
            return ("RAG no disponible (índice vacío). Ejecutá el ingest: "
                    "python -m advanced_agent.rag.ingest")
        k = top_k or ctx.config.rag.get("top_k", 4)
        hits = ctx.rag.search(query, top_k=k)
        ctx.tracer.log_retrieval(query, hits)
        if not hits:
            return "RAG: sin coincidencias relevantes."

        min_score = ctx.config.rag.get("min_score", 0.2)
        sufficient = any(h["score"] >= min_score for h in hits)
        lines = [f"RAG: {len(hits)} fragmentos recuperados para «{query}» "
                 f"(evidencia {'SUFICIENTE' if sufficient else 'DÉBIL → considerar web'}):"]
        for i, h in enumerate(hits, 1):
            ctx.state.add_source(Source(SourceKind.RAG, h["source"],
                                        h["text"][:200], score=h["score"]))
            lines.append(
                f"\n[{i}] fuente: {h['source']}  (score={h['score']:.3f})\n"
                f"    «{h['text'][:400].strip()}»"
            )
        if not sufficient:
            ctx.state.observe("RAG con baja evidencia: el Researcher debería ir a la web.")
        return "\n".join(lines)
