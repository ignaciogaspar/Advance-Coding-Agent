"""Tests offline (sin red ni claves) de los componentes del sistema.

Verifican: motor de políticas, descubrimiento de plugins, chunking + RAG con
embeddings mock, detección de loops y memoria persistente.

Correr:  pytest -q  (desde la raíz del proyecto)
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from advanced_agent.core.config import load_config, PolicyEngine, PermissionDenied
from advanced_agent.core.observability import Tracer
from advanced_agent.core.llm import LLMClient
from advanced_agent.core.state import TaskState
from advanced_agent.rag.index import chunk_text, RagIndex
from advanced_agent.memory.project_memory import ProjectMemory
from advanced_agent.agents.base_agent import LoopDetector


def _cfg():
    return load_config(str(ROOT / "agent.config.yaml"))


def test_policy_blocks_secrets_and_commands():
    pol = PolicyEngine(_cfg())
    assert pol.check_read(".env").allowed is False
    assert pol.check_read("app/main.py").allowed is True
    assert pol.check_write("package-lock.json").allowed is False
    assert pol.check_write("app/new.py").allowed is True
    assert pol.check_command("rm -rf /").allowed is False
    d = pol.check_command("pip install fastapi")
    assert d.allowed is True and d.needs_approval is True


def test_policy_blocks_path_traversal():
    pol = PolicyEngine(_cfg())
    try:
        pol.enforce_read("../../etc/passwd")
        assert False, "debería haber denegado el path traversal"
    except PermissionDenied:
        pass


def test_plugin_discovery_finds_all_tools():
    from advanced_agent.tools.base import ToolRegistry, ToolContext
    cfg = _cfg()
    tracer = Tracer({"enabled": False}, run_name="test")
    state = TaskState()
    ctx = ToolContext(config=cfg, policy=PolicyEngine(cfg), state=state, tracer=tracer)
    reg = ToolRegistry(ctx)
    names = set(reg.names())
    expected = {"read_file", "write_file", "run_command", "list_files",
                "web_search", "rag_search", "memory_read", "memory_write"}
    assert expected.issubset(names), f"faltan tools: {expected - names}"


def test_chunking_overlap():
    text = "párrafo uno.\n\n" + ("palabra " * 300)
    chunks = chunk_text(text, "doc.md", chunk_size=200, overlap=50)
    assert len(chunks) > 1
    assert all(c["source"] == "doc.md" for c in chunks)


def test_rag_retrieval_with_mock_embeddings(tmp_path):
    tracer = Tracer({"enabled": False}, run_name="test")
    llm = LLMClient("gpt-4o-mini", "text-embedding-3-small", tracer, mock=True)
    idx = RagIndex(index_path=tmp_path / "idx.json", llm=llm, chunk_size=300, overlap=50)
    meta = idx.build(ROOT / "rag_corpus")
    assert meta["n_chunks"] > 0
    hits = idx.search("how to declare a request body with pydantic", top_k=3)
    assert hits and "score" in hits[0]
    # El término "pydantic" debería traer el doc de request body.
    assert any("pydantic" in h["source"].lower() or "body" in h["source"].lower()
               for h in hits)


def test_loop_detector():
    ld = LoopDetector(window=3)
    assert ld.record("run:pytest", "FAILED x") is False
    assert ld.record("run:pytest", "FAILED x") is False
    assert ld.record("run:pytest", "FAILED x") is True   # 3 idénticas → loop


def test_memory_persists(tmp_path):
    mem = ProjectMemory(tmp_path / "mem.json")
    assert mem.is_empty()
    mem.add("architecture", "FastAPI con router /tasks")
    mem.add("dependencies", "fastapi, uvicorn, pytest")
    mem2 = ProjectMemory(tmp_path / "mem.json")   # recargar de disco
    assert "FastAPI con router /tasks" in mem2.get("architecture")
    assert not mem2.is_empty()


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
