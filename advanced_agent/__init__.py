"""Coding Agent Avanzado — sistema multi-agente sin frameworks de orquestación.

Autores: Marco Schenker, Ignacio Gaspar.
"""
__version__ = "1.0.0"

# Carga automática del .env (si existe) para que demos y CLI encuentren las
# claves sin necesidad de exportarlas manualmente. No pisa variables ya seteadas.
import os as _os


def _load_dotenv(path: str = ".env") -> None:
    if _os.path.exists(path):
        for _line in open(path, encoding="utf-8"):
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                _os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))


_load_dotenv()
