"""Carga y validación de la configuración del agente (agent.config.yaml).

Incluye el PolicyEngine: el componente que decide, ANTES de cada tool call,
si una operación está permitida, denegada, o requiere aprobación humana.
"""
from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path

import yaml


class ConfigError(Exception):
    pass


class PermissionDenied(Exception):
    """Se lanza cuando una política deniega una operación."""
    def __init__(self, message: str, *, kind: str, target: str):
        super().__init__(message)
        self.kind = kind
        self.target = target


class ApprovalRequired(Exception):
    """Se lanza cuando una operación necesita aprobación humana.

    El harness la captura y pregunta al usuario (o la deniega en modo no
    interactivo)."""
    def __init__(self, message: str, *, command: str):
        super().__init__(message)
        self.command = command


@dataclass
class PolicyDecision:
    allowed: bool
    needs_approval: bool = False
    reason: str = ""


class PolicyEngine:
    """Evalúa las políticas de lectura, escritura y comandos.

    Reglas:
      - `deny` siempre gana. Para lecturas/escrituras se hace match glob contra
        el path relativo al workspace; para comandos, match por substring.
      - Todo path debe estar DENTRO del workspace (defensa anti path-traversal).
      - `require_approval` marca comandos que el usuario debe autorizar.
    """

    def __init__(self, config: "AgentConfig"):
        self.cfg = config
        self.workspace = config.workspace.resolve()
        perms = config.raw.get("permissions", {})
        self.read_deny = perms.get("read", {}).get("deny", []) or []
        self.write_deny = perms.get("write", {}).get("deny", []) or []
        cmds = config.raw.get("commands", {})
        self.cmd_deny = cmds.get("deny", []) or []
        self.cmd_approval = cmds.get("require_approval", []) or []

    # ---------- helpers ----------
    def _within_workspace(self, path: str) -> Path:
        p = (self.workspace / path).resolve() if not os.path.isabs(path) else Path(path).resolve()
        try:
            p.relative_to(self.workspace)
        except ValueError:
            raise PermissionDenied(
                f"Ruta fuera del workspace: {path}", kind="path", target=path
            )
        return p

    def _rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.workspace))
        except ValueError:
            return str(path)

    @staticmethod
    def _matches(rel_path: str, patterns: list[str]) -> str | None:
        """Devuelve el patrón que matchea, o None. Soporta glob simple y `**`."""
        candidates = {rel_path, os.path.basename(rel_path)}
        for pat in patterns:
            for cand in candidates:
                if fnmatch.fnmatch(cand, pat):
                    return pat
            # `**` glob: fnmatch no expande **, así que probamos también
            # con el patrón "aplanado" para subdirectorios.
            if "**" in pat and fnmatch.fnmatch(rel_path, pat.replace("**", "*")):
                return pat
            if pat.endswith("/**") and rel_path.startswith(pat[:-3].rstrip("/") + "/"):
                return pat
        return None

    # ---------- decisiones ----------
    def check_read(self, path: str) -> PolicyDecision:
        p = self._within_workspace(path)
        rel = self._rel(p)
        hit = self._matches(rel, self.read_deny)
        if hit:
            return PolicyDecision(False, reason=f"lectura denegada por política '{hit}'")
        return PolicyDecision(True)

    def check_write(self, path: str) -> PolicyDecision:
        p = self._within_workspace(path)
        rel = self._rel(p)
        hit = self._matches(rel, self.write_deny)
        if hit:
            return PolicyDecision(False, reason=f"escritura denegada por política '{hit}'")
        return PolicyDecision(True)

    def check_command(self, command: str) -> PolicyDecision:
        for bad in self.cmd_deny:
            if bad in command:
                return PolicyDecision(False, reason=f"comando denegado por política '{bad}'")
        for needs in self.cmd_approval:
            if needs in command:
                return PolicyDecision(True, needs_approval=True,
                                      reason=f"requiere aprobación por política '{needs}'")
        return PolicyDecision(True)

    def enforce_read(self, path: str) -> Path:
        d = self.check_read(path)
        if not d.allowed:
            raise PermissionDenied(d.reason, kind="read", target=path)
        return self._within_workspace(path)

    def enforce_write(self, path: str) -> Path:
        d = self.check_write(path)
        if not d.allowed:
            raise PermissionDenied(d.reason, kind="write", target=path)
        return self._within_workspace(path)


@dataclass
class AgentConfig:
    raw: dict
    path: Path

    @property
    def workspace(self) -> Path:
        base = self.path.parent
        return (base / self.raw.get("workspace", ".")).resolve()

    @property
    def chat_model(self) -> str:
        return self.raw.get("models", {}).get("chat", "gpt-4o-mini")

    @property
    def embed_model(self) -> str:
        return self.raw.get("models", {}).get("embeddings", "text-embedding-3-small")

    @property
    def limits(self) -> dict:
        return self.raw.get("limits", {})

    @property
    def rag(self) -> dict:
        return self.raw.get("rag", {})

    @property
    def memory_path(self) -> Path:
        base = self.path.parent
        return (base / self.raw.get("memory", {}).get("path", "./data/project_memory.json")).resolve()

    @property
    def observability(self) -> dict:
        return self.raw.get("observability", {})

    def resolve(self, rel: str) -> Path:
        return (self.path.parent / rel).resolve()


REQUIRED_TOP_KEYS = ["workspace", "models", "permissions", "commands"]


def load_config(path: str | os.PathLike = "agent.config.yaml") -> AgentConfig:
    """Carga y valida el YAML. Lanza ConfigError si falta algo esencial."""
    p = Path(path).resolve()
    if not p.exists():
        raise ConfigError(f"No se encontró el archivo de configuración: {p}")
    with open(p, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    missing = [k for k in REQUIRED_TOP_KEYS if k not in raw]
    if missing:
        raise ConfigError(f"Faltan claves obligatorias en la config: {missing}")

    cfg = AgentConfig(raw=raw, path=p)
    # Validar que el workspace exista (se crea si no, para no fallar en seco).
    cfg.workspace.mkdir(parents=True, exist_ok=True)
    cfg.memory_path.parent.mkdir(parents=True, exist_ok=True)
    return cfg
