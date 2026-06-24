"""DEMO 2 — Tarea que usa la memoria persistente del proyecto.

Primera corrida: el Explorer detecta la arquitectura y la guarda en memoria.
Segunda corrida: se crea un sistema NUEVO (estado fresco) que lee la memoria
persistida en disco — demostrando que el conocimiento sobrevive entre sesiones.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
os.chdir(ROOT)

from advanced_agent.system import AgentSystem
from advanced_agent.memory.project_memory import ProjectMemory
from mock_brains import make_memory_demo_brain   # noqa: E402


def main():
    use_mock = not os.environ.get("OPENAI_API_KEY")

    print("=" * 70)
    print("DEMO 2 — Memoria persistente del proyecto")
    print("=" * 70)

    # Empezar de cero para que la demo sea reproducible (reset del contenido).
    mem_path = ROOT / "data" / "project_memory.json"
    mem_path.parent.mkdir(parents=True, exist_ok=True)
    ProjectMemory(mem_path)._reset()

    # ---- Sesión 1: detectar y guardar arquitectura ----
    print("\n>>> SESIÓN 1: el Explorer detecta y guarda la arquitectura en memoria")
    s1 = AgentSystem("agent.config.yaml", interactive=False,
                     mock=True if use_mock else None,
                     mock_handler=make_memory_demo_brain() if use_mock else None,
                     run_name="demo-2-mem-s1")
    s1.run("Analizá la arquitectura del repositorio y recordala para futuras sesiones.")

    print("\nMemoria persistida en disco:")
    print(ProjectMemory(mem_path).summary())

    # ---- Sesión 2: sistema nuevo que LEE la memoria existente ----
    print("\n>>> SESIÓN 2: un sistema NUEVO arranca y ya conoce el proyecto")
    s2 = AgentSystem("agent.config.yaml", interactive=False, mock=True,
                     mock_handler=lambda m, t: {"content": '{"action":"finish",'
                     '"final":"Ya conozco la arquitectura por memoria de la sesión previa."}',
                     "raw": None, "tool_calls": []},
                     run_name="demo-2-mem-s2")
    loaded = s2.memory.summary()
    print("\nLo que el sistema nuevo recuerda al arrancar:")
    print(loaded)
    assert "architecture" in loaded or "FastAPI" in loaded, "la memoria no persistió"
    print("\n[OK] La memoria del proyecto persistió entre sesiones.")
    print(f"Trace: {s2.tracer.trace_id}")


if __name__ == "__main__":
    main()
