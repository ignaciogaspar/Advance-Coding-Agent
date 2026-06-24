"""Tools de filesystem — preservadas del coding agent original del TP en clase,
ahora con validación de políticas y registro de fuentes en el estado.

Tools: read_file, write_file, list_files. (Conservan la semántica original
read/write/explore del harness.)
"""
from __future__ import annotations

import os

from ..base import Tool, ToolContext
from ...core.state import Source, SourceKind


class ReadFileTool(Tool):
    name = "read_file"
    description = "Lee el contenido de un archivo del repositorio (relativo al workspace)."
    permission = "read"
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Ruta del archivo."}},
        "required": ["path"],
    }

    def run(self, ctx: ToolContext, path: str) -> str:
        resolved = ctx.policy.enforce_read(path)   # valida política + workspace
        if not resolved.exists():
            return f"Error: no existe el archivo {path}"
        try:
            content = resolved.read_text(encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            return f"Error leyendo archivo: {e}"
        ctx.state.add_source(Source(SourceKind.REPO, path, "leído del repositorio"))
        # Truncar para no inundar el contexto (la consigna pide no mandar todo).
        if len(content) > 6000:
            return content[:6000] + f"\n... [truncado, {len(content)} chars en total]"
        return content


class WriteFileTool(Tool):
    name = "write_file"
    description = "Escribe/crea un archivo en el workspace. Sujeto a política de escritura."
    permission = "write"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Ruta del archivo."},
            "content": {"type": "string", "description": "Contenido a escribir."},
        },
        "required": ["path", "content"],
    }

    def run(self, ctx: ToolContext, path: str, content: str) -> str:
        resolved = ctx.policy.enforce_write(path)   # valida política + workspace
        resolved.parent.mkdir(parents=True, exist_ok=True)
        try:
            resolved.write_text(content, encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            return f"Error escribiendo archivo: {e}"
        ctx.state.record_modified(path)
        return f"Éxito: archivo {path} escrito ({len(content)} chars)."


class ListFilesTool(Tool):
    name = "list_files"
    description = ("Lista archivos y carpetas. Soporta recursivo para entender la "
                   "estructura del repositorio.")
    permission = "read"
    parameters = {
        "type": "object",
        "properties": {
            "directory": {"type": "string", "description": "Directorio (default '.')."},
            "recursive": {"type": "boolean", "description": "Listar recursivamente."},
        },
    }

    def run(self, ctx: ToolContext, directory: str = ".", recursive: bool = False) -> str:
        base = ctx.policy.enforce_read(directory)
        if not base.exists():
            return f"Error: no existe el directorio {directory}"
        out = []
        if recursive:
            for root, dirs, files in os.walk(base):
                # No descender en directorios ruidosos.
                dirs[:] = [d for d in dirs if d not in
                           {".git", "__pycache__", "node_modules", ".venv", "venv"}]
                rel_root = os.path.relpath(root, base)
                for f in sorted(files):
                    out.append(os.path.join(rel_root, f) if rel_root != "." else f)
            out = out[:200]   # cota de seguridad
        else:
            for item in sorted(base.iterdir()):
                out.append(item.name + ("/" if item.is_dir() else ""))
        ctx.state.add_source(Source(SourceKind.REPO, directory, "listado de directorio"))
        return "\n".join(out) if out else "(vacío)"
