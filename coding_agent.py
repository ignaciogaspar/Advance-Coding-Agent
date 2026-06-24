"""
Coding Agent
============
Un agente de código impulsado por un LLM (OpenAI) capaz de:
  - Clonar y explorar repositorios de GitHub.
  - Leer, analizar y modificar archivos de código.
  - Ejecutar tareas de forma autónoma a partir de instrucciones en lenguaje natural.

Características del harness:
  - Plan Mode: el agente propone primero un plan (sin usar herramientas) que el
    usuario aprueba antes de la ejecución.
  - Supervision Mode: las herramientas sensibles (write_file, run_command)
    requieren autorización explícita del usuario antes de ejecutarse.
  - Bucle agéntico con tope de iteraciones (max_iterations) para evitar bucles
    infinitos.

Autores: Marco Schenker, Ignacio Gaspar.

Nota sobre correcciones aplicadas frente al notebook original:
  1. La última línea `start_coding_agent(ç)` contenía un carácter inválido (`ç`)
     que provocaba un NameError. Se reemplaza por una llamada válida bajo el
     guardia `if __name__ == "__main__":`.
  2. Se añade un parámetro `model` configurable y se documenta la dependencia de
     las variables de entorno OPENAI_API_KEY y TAVILY_API_KEY.
  3. Se evita serializar el objeto `msg` de OpenAI directamente en el historial:
     se reconstruye un dict con el rol "assistant" y sus tool_calls, lo que hace
     el historial portable y reproducible.
  4. web_search usa el campo `content` (más informativo) además del título/URL.
"""

import os
import json
import subprocess

from openai import OpenAI

# ==========================================
# CONFIGURACIÓN DEL CLIENTE
# ==========================================
# Las claves se leen del entorno. Exporta antes de ejecutar:
#   export OPENAI_API_KEY="sk-..."
#   export TAVILY_API_KEY="tvly-..."
MODEL = os.environ.get("AGENT_MODEL", "gpt-5-nano")

# El cliente se crea de forma perezosa para que el módulo pueda importarse y
# probarse sin una clave válida ni acceso de red.
_client = None


def get_client():
    """Devuelve un cliente OpenAI, creándolo la primera vez que se usa."""
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return _client


# ==========================================
# 1. DEFINICIÓN DE HERRAMIENTAS (TOOLS)
# ==========================================

def read_file(filepath):
    """Lee el contenido de un archivo."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error leyendo archivo: {e}"


def write_file(filepath, content):
    """Escribe contenido en un archivo (crea directorios padre si hace falta)."""
    try:
        parent = os.path.dirname(filepath)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Éxito: Archivo {filepath} modificado."
    except Exception as e:
        return f"Error escribiendo archivo: {e}"


def run_command(command):
    """Ejecuta un comando de terminal y devuelve stdout + stderr."""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True
        )
        output = result.stdout
        if result.stderr:
            output += f"\nError/Stderr: {result.stderr}"
        return output if output.strip() else "Comando ejecutado con éxito (sin salida)."
    except Exception as e:
        return f"Error ejecutando comando: {e}"


def list_files(directory="."):
    """Lista los archivos en un directorio."""
    try:
        return "\n".join(sorted(os.listdir(directory)))
    except Exception as e:
        return f"Error listando directorio: {e}"


def web_search(query):
    """Busca información en la web usando la API de Tavily."""
    import requests

    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return "Error: No TAVILY_API_KEY."
    url = "https://api.tavily.com/search"
    payload = {"api_key": api_key, "query": query, "max_results": 3}
    try:
        response = requests.post(url, json=payload, timeout=15)
        data = response.json()
        results = data.get("results", [])
        if not results:
            return "Sin resultados."
        lines = []
        for r in results:
            snippet = (r.get("content") or "").strip().replace("\n", " ")
            lines.append(f"- {r.get('title')} ({r.get('url')})\n  {snippet[:300]}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


available_tools = {
    "read_file": read_file,
    "write_file": write_file,
    "run_command": run_command,
    "list_files": list_files,
    "web_search": web_search,
}

tools_schema = [
    {"type": "function", "function": {"name": "read_file", "description": "Lee un archivo.",
        "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}},
                       "required": ["filepath"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Escribe un archivo.",
        "parameters": {"type": "object", "properties": {"filepath": {"type": "string"},
                       "content": {"type": "string"}}, "required": ["filepath", "content"]}}},
    {"type": "function", "function": {"name": "run_command", "description": "Ejecuta comando bash.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}},
                       "required": ["command"]}}},
    {"type": "function", "function": {"name": "list_files", "description": "Lista archivos.",
        "parameters": {"type": "object", "properties": {"directory": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "web_search", "description": "Busca en la web.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                       "required": ["query"]}}},
]


# ==========================================
# 2. EL HARNESS DEL AGENTE
# ==========================================

SYSTEM_PROMPT = (
    "Eres un Agente de Código. Si plan_mode está activo, primero generarás un "
    "plan sin usar herramientas. Una vez aprobado, ejecutarás las herramientas "
    "necesarias para completar la tarea."
)


def start_coding_agent(plan_mode=True, supervision_mode=True, max_iterations=10):
    """Bucle interactivo del agente.

    Args:
        plan_mode: si es True, el agente propone un plan que debe aprobarse.
        supervision_mode: si es True, write_file y run_command piden autorización.
        max_iterations: tope de pasos de la fase de ejecución.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    print(f"🤖 Agent Started. Plan Mode: {plan_mode} | "
          f"Supervisión: {supervision_mode} | Max Iters: {max_iterations}")

    while True:
        user_input = input("\n👤 Tú: ")
        if user_input.lower() in ["salir", "exit"]:
            break
        messages.append({"role": "user", "content": user_input})

        # -------- FASE DE PLANIFICACIÓN --------
        if plan_mode:
            try:
                print("\n[Pensando Plan...]")
                res = get_client().chat.completions.create(
                    model=MODEL,
                    messages=messages + [{"role": "system",
                        "content": "Genera un plan detallado. NO uses herramientas todavía."}],
                )
                plan = res.choices[0].message.content
                print(f"\n📝 PLAN:\n{plan}")

                feedback = input("\n❓ ¿Aprobar? (s/n/comentario): ")
                if feedback.lower() != "s":
                    messages.append({"role": "assistant", "content": plan})
                    messages.append({"role": "user",
                        "content": f"Plan rechazado/modificado: {feedback}"})
                    continue

                messages.append({"role": "assistant", "content": plan})
                messages.append({"role": "user",
                    "content": "Plan aprobado. PROCEDE CON LA EJECUCIÓN USANDO HERRAMIENTAS."})
            except Exception as e:
                print(f"Error: {e}")
                continue

        # -------- FASE DE EJECUCIÓN --------
        for i in range(1, max_iterations + 1):
            print(f"\n[Log] Iteración {i}/{max_iterations}...")
            try:
                response = get_client().chat.completions.create(
                    model=MODEL, messages=messages, tools=tools_schema
                )
                msg = response.choices[0].message

                # Sin tool_calls -> respuesta final del agente.
                if not msg.tool_calls:
                    messages.append({"role": "assistant", "content": msg.content})
                    print(f"\n🤖 Agente: {msg.content}")
                    break

                # Reconstruimos el mensaje assistant con sus tool_calls (portable).
                messages.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [{
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name,
                                     "arguments": tc.function.arguments},
                    } for tc in msg.tool_calls],
                })

                for tool_call in msg.tool_calls:
                    name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    print(f"⚡ Tool: {name}({args})")

                    if supervision_mode and name in ["write_file", "run_command"]:
                        if input(f"⚠️  ¿Autorizar {name}? (s/n): ").lower() != "s":
                            result = "Error: Usuario denegó ejecución."
                        else:
                            result = available_tools[name](**args)
                    else:
                        result = available_tools[name](**args)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": name,
                        "content": str(result),
                    })
            except Exception as e:
                print(f"❌ Error: {e}")
                break
        else:
            print("⚠️ Límite alcanzado.")


if __name__ == "__main__":
    start_coding_agent(plan_mode=True, supervision_mode=True, max_iterations=10)
