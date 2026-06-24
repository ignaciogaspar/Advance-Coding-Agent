"""Memoria persistente del proyecto (distinta del historial de conversación).

Almacena hechos que sobreviven entre sesiones, organizados por secciones:
arquitectura detectada, archivos importantes, dependencias, comandos útiles,
convenciones, decisiones tomadas, bugs investigados y resúmenes de sesiones
anteriores. Se persiste en un JSON simple.
"""
from __future__ import annotations

import json
import time
from pathlib import Path


class ProjectMemory:
    SECTIONS = [
        "architecture",        # arquitectura detectada
        "key_files",           # archivos importantes
        "dependencies",        # dependencias
        "commands",            # comandos útiles
        "conventions",         # convenciones
        "decisions",           # decisiones tomadas
        "bugs",                # bugs investigados
        "session_summaries",   # resúmenes de sesiones anteriores
    ]

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.data: dict = {s: [] for s in self.SECTIONS}
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                stored = json.loads(self.path.read_text(encoding="utf-8"))
                for s in self.SECTIONS:
                    self.data[s] = stored.get(s, [])
            except Exception:  # noqa: BLE001
                pass

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False),
                             encoding="utf-8")

    def _reset(self) -> None:
        """Vacía la memoria (útil para demos reproducibles)."""
        self.data = {s: [] for s in self.SECTIONS}
        self.save()

    def add(self, section: str, content: str) -> bool:
        if section not in self.SECTIONS:
            return False
        entry = {"content": content, "ts": time.time()}
        # Evitar duplicados exactos.
        if not any(e.get("content") == content for e in self.data[section]):
            self.data[section].append(entry)
            self.save()
        return True

    def get(self, section: str) -> list[str]:
        return [e["content"] for e in self.data.get(section, [])]

    def is_empty(self) -> bool:
        return all(len(v) == 0 for v in self.data.values())

    def summary(self, max_per_section: int = 5) -> str:
        if self.is_empty():
            return "Memoria del proyecto: (vacía — primera sesión)."
        parts = ["=== MEMORIA PERSISTENTE DEL PROYECTO ==="]
        for s in self.SECTIONS:
            items = self.get(s)
            if items:
                shown = items[-max_per_section:]
                parts.append(f"\n[{s}]")
                parts.extend(f"  - {c}" for c in shown)
        return "\n".join(parts)

    def record_session_summary(self, request: str, outcome: str) -> None:
        ts = time.strftime("%Y-%m-%d %H:%M")
        self.add("session_summaries", f"{ts} — Pedido: «{request[:80]}» → {outcome[:160]}")
