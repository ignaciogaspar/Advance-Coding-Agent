"""Tool de ejecución de comandos — preservada del harness original, ahora con
política de comandos (deny / require_approval) validada antes de ejecutar.
"""
from __future__ import annotations

import os
import subprocess

from ..base import Tool, ToolContext


class RunCommandTool(Tool):
    name = "run_command"
    description = ("Ejecuta un comando de shell dentro del workspace y devuelve "
                   "stdout + stderr. Sujeto a la política de comandos.")
    permission = "command"
    parameters = {
        "type": "object",
        "properties": {"command": {"type": "string", "description": "Comando a ejecutar."}},
        "required": ["command"],
    }

    def run(self, ctx: ToolContext, command: str) -> str:
        cwd = str(ctx.config.workspace)
        env = os.environ.copy()
        # El binario `pytest` (a diferencia de `python -m pytest`) NO agrega el
        # directorio actual a sys.path, así que un test que hace
        # `from app.models import ...` falla con ModuleNotFoundError aunque la
        # estructura de carpetas sea correcta. Como el workspace es la raíz
        # del proyecto del usuario, lo agregamos siempre a PYTHONPATH para que
        # cualquier comando Python (pytest, un script suelto, etc.) pueda
        # importar los paquetes top-level del proyecto sin que el subagente
        # tenga que acordarse de invocarlo de una forma particular.
        env["PYTHONPATH"] = cwd + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                cwd=cwd, timeout=120, env=env,
            )
        except subprocess.TimeoutExpired:
            return "Error: el comando excedió el timeout (120s)."
        except Exception as e:  # noqa: BLE001
            return f"Error ejecutando comando: {e}"
        output = result.stdout or ""
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        output += f"\n[exit={result.returncode}]"
        return output.strip() or "Comando ejecutado (sin salida)."