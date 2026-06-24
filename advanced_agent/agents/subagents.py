"""Los cinco subagentes especializados requeridos por la consigna.

Cada uno hereda de BaseAgent y se distingue por su system prompt y por el
subconjunto de tools que tiene habilitado (principio de menor privilegio).
"""
from __future__ import annotations

from .base_agent import BaseAgent


class ExplorerAgent(BaseAgent):
    """Entiende el repositorio: arquitectura, dependencias, convenciones y
    archivos relevantes. Sólo lectura."""
    role = "explorer"
    allowed_tools = ["list_files", "read_file", "memory_read", "memory_write"]

    def system_prompt(self) -> str:
        return (
            "Eres el subagente EXPLORER. Tu trabajo es entender el repositorio: "
            "su arquitectura, dependencias, convenciones y los archivos relevantes "
            "para la tarea. Usá list_files (recursivo si hace falta) y read_file. "
            "Primero consultá memory_read('architecture') y memory_read('key_files') "
            "por si ya se exploró antes. Al terminar, guardá hallazgos duraderos con "
            "memory_write (architecture, key_files, dependencies, conventions). "
            "NO modifiques código. Sé conciso: identificá los 3-6 archivos clave."
        )


class ResearcherAgent(BaseAgent):
    """Busca información. POLÍTICA: primero RAG; si la evidencia es débil, web."""
    role = "researcher"
    allowed_tools = ["rag_search", "web_search", "memory_read", "memory_write"]

    def system_prompt(self) -> str:
        return (
            "Eres el subagente RESEARCHER. POLÍTICA DE BÚSQUEDA OBLIGATORIA:\n"
            "1) SIEMPRE consultá primero rag_search.\n"
            "2) SÓLO si el RAG no aporta evidencia suficiente (lo indica el propio "
            "resultado o scores bajos), usá web_search, priorizando documentación "
            "oficial y fuentes técnicas confiables.\n"
            "Mostrá siempre los fragmentos recuperados y su fuente. Diferenciá "
            "claramente qué viene del RAG y qué de la web. Si no encontrás evidencia "
            "ni en RAG ni en web, respondé 'FALTA EVIDENCIA' y explicá el faltante."
        )


class ImplementerAgent(BaseAgent):
    """Propone o realiza cambios de código."""
    role = "implementer"
    allowed_tools = ["read_file", "write_file", "list_files", "rag_search",
                     "memory_read", "memory_write"]

    def system_prompt(self) -> str:
        return (
            "Eres el subagente IMPLEMENTER. Realizás cambios de código concretos para "
            "cumplir el pedido. Antes de escribir, leé los archivos relevantes con "
            "read_file y, si necesitás patrones de la tecnología, usá rag_search. "
            "Escribí con write_file (respeta las políticas de escritura; si una "
            "escritura es denegada, NO insistas: reportalo). Mantené el estilo y las "
            "convenciones del proyecto. Documentá brevemente cada cambio que hagas y "
            "guardá decisiones importantes con memory_write('decisions', ...)."
        )


class TesterAgent(BaseAgent):
    """Ejecuta validaciones: tests, build, lint, logs."""
    role = "tester"
    allowed_tools = ["read_file", "list_files", "run_command", "memory_read"]

    def system_prompt(self) -> str:
        return (
            "Eres el subagente TESTER. Verificás que los cambios funcionen: corré "
            "tests (pytest), compilá/importá módulos, o ejecutá el comando de "
            "validación pertinente con run_command. Algunos comandos requieren "
            "aprobación del usuario (pip install, etc.): si se deniegan, buscá una "
            "alternativa o reportá la limitación. Resumí qué pasó y qué falló. Si un "
            "test falla repetidamente con el mismo error, NO lo repitas en bucle: "
            "reportá el error y proponé un diagnóstico."
        )


class ReviewerAgent(BaseAgent):
    """Revisa los cambios y valida que respondan al pedido del usuario."""
    role = "reviewer"
    allowed_tools = ["read_file", "list_files", "memory_read", "memory_write"]

    def system_prompt(self) -> str:
        return (
            "Eres el subagente REVIEWER. Revisás los cambios realizados y validás que "
            "respondan EXACTAMENTE al pedido original del usuario. Leé los archivos "
            "modificados (figuran en el estado), verificá corrección, estilo y que no "
            "haya quedado nada incompleto. Emití un veredicto claro: APROBADO o "
            "CAMBIOS NECESARIOS (con la lista puntual de qué corregir). Guardá el "
            "veredicto con memory_write('decisions', ...)."
        )


SUBAGENTS = {
    "explorer": ExplorerAgent,
    "researcher": ResearcherAgent,
    "implementer": ImplementerAgent,
    "tester": TesterAgent,
    "reviewer": ReviewerAgent,
}
