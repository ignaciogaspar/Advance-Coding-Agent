"""DEMO 3 — Tarea donde el agente cambia de estrategia / se detiene / pide ayuda.

El pedido exige integrar un sistema propietario del que NO hay documentación ni
en el RAG ni en la web. El Researcher declara 'FALTA EVIDENCIA' y el orquestador
toma la acción 'need_user': explica qué intentó, qué falta y qué necesita.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
os.chdir(ROOT)

from advanced_agent.system import AgentSystem
from mock_brains import make_block_demo_brain   # noqa: E402


def main():
    use_mock = not os.environ.get("OPENAI_API_KEY")

    print("=" * 70)
    print("DEMO 3 — Falta de evidencia: el agente se detiene y pide ayuda")
    print("=" * 70)

    system = AgentSystem("agent.config.yaml", interactive=False,
                         mock=True if use_mock else None,
                         mock_handler=make_block_demo_brain() if use_mock else None,
                         run_name="demo-3-block")

    request = ("Integrá la API con el sistema propietario interno 'XYZ-Mainframe' "
               "usando su protocolo privado no documentado.")
    answer = system.run(request)

    print("\n--- RESPUESTA FINAL ---\n" + answer)
    print(f"\nEstado final: {system.state.status}")
    print("\n--- OBSERVACIONES (por qué se detuvo) ---")
    for o in system.state.observations:
        print(f"  - {o}")
    assert system.state.status in {"blocked"}, "se esperaba estado 'blocked'"
    print("\n[OK] El agente reconoció la falta de evidencia y pidió ayuda "
          "en lugar de inventar una solución.")
    print(f"Trace: {system.tracer.trace_id}")


if __name__ == "__main__":
    main()
