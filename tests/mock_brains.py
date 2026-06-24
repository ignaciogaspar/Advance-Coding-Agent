"""Cerebros mock (deterministas) para correr las demos SIN claves de API.

Cada función es un `mock_handler` que recibe (messages, tools) y devuelve la
misma forma que LLMClient.chat: {content, tool_calls, raw}. Simulan las
decisiones del orquestador y de los subagentes para que las demos sean
reproducibles en CI. Con claves reales, NO se usan estos mocks (el sistema
llama a OpenAI de verdad).

El estado avanza mediante un contador en una lista mutable capturada en la
clausura, así cada llamada produce el siguiente paso del guion.
"""
import json


def _last_system(messages):
    for m in messages:
        if m["role"] == "system":
            return m["content"]
    return ""


def make_rag_demo_brain():
    """Demo 1: el orquestador delega en researcher, que usa rag_search."""
    step = {"n": 0}

    def brain(messages, tools):
        sys = _last_system(messages)
        # --- subagente researcher: pedir rag_search una vez, luego responder ---
        if "RESEARCHER" in sys:
            # ¿ya hay un resultado de tool en el historial?
            has_tool = any(m.get("role") == "tool" for m in messages)
            if not has_tool:
                return {"content": None, "raw": None, "tool_calls": [
                    {"id": "c1", "name": "rag_search",
                     "arguments": {"query": "FastAPI request body Pydantic response_model"}}]}
            return {"content": ("Según el RAG, en FastAPI el request body se declara con "
                                "modelos Pydantic (BaseModel) y la salida se filtra con "
                                "response_model. Fuentes recuperadas del índice RAG."),
                    "raw": None, "tool_calls": []}
        # --- orquestador ---
        if "AGENTE PRINCIPAL" in sys:
            step["n"] += 1
            if step["n"] == 1:
                return {"content": json.dumps({
                    "action": "delegate", "agent": "researcher",
                    "instruction": "Buscá en el RAG cómo se manejan request body y "
                                   "response_model en FastAPI; mostrá fuentes."}),
                    "raw": None, "tool_calls": []}
            return {"content": json.dumps({
                "action": "finish",
                "final": "Resumen entregado con evidencia del RAG (request body Pydantic "
                         "+ response_model). Ver fuentes RAG en el estado."}),
                "raw": None, "tool_calls": []}
        return {"content": "[mock]", "raw": None, "tool_calls": []}

    return brain


def make_memory_demo_brain():
    """Demo 2: explorer escribe memoria; un segundo turno la lee."""
    step = {"n": 0}

    def brain(messages, tools):
        sys = _last_system(messages)
        if "EXPLORER" in sys:
            has_tool = any(m.get("role") == "tool" for m in messages)
            if not has_tool:
                return {"content": None, "raw": None, "tool_calls": [
                    {"id": "m1", "name": "memory_write",
                     "arguments": {"section": "architecture",
                                   "content": "API FastAPI con router /tasks y modelos Pydantic"}},
                    {"id": "m2", "name": "memory_write",
                     "arguments": {"section": "key_files",
                                   "content": "app/main.py, app/routers/tasks.py, app/models.py"}}]}
            return {"content": "Arquitectura registrada en memoria del proyecto.",
                    "raw": None, "tool_calls": []}
        if "AGENTE PRINCIPAL" in sys:
            step["n"] += 1
            if step["n"] == 1:
                return {"content": json.dumps({
                    "action": "delegate", "agent": "explorer",
                    "instruction": "Detectá la arquitectura y archivos clave y guardalos en memoria."}),
                    "raw": None, "tool_calls": []}
            return {"content": json.dumps({
                "action": "finish",
                "final": "Arquitectura detectada y persistida en memoria para futuras sesiones."}),
                "raw": None, "tool_calls": []}
        return {"content": "[mock]", "raw": None, "tool_calls": []}

    return brain


def make_block_demo_brain():
    """Demo 3: el researcher no encuentra evidencia y declara FALTA EVIDENCIA;
    el orquestador entonces pide ayuda al usuario (need_user)."""
    step = {"n": 0}

    def brain(messages, tools):
        sys = _last_system(messages)
        if "RESEARCHER" in sys:
            has_tool = any(m.get("role") == "tool" for m in messages)
            if not has_tool:
                return {"content": None, "raw": None, "tool_calls": [
                    {"id": "r1", "name": "rag_search",
                     "arguments": {"query": "integración con base de datos Oracle propietaria XYZ"}}]}
            return {"content": ("FALTA EVIDENCIA: ni el RAG ni la documentación cubren la "
                                "integración propietaria solicitada. Intenté rag_search sin "
                                "resultados relevantes. Necesito documentación específica o "
                                "credenciales del sistema XYZ para continuar."),
                    "raw": None, "tool_calls": []}
        if "AGENTE PRINCIPAL" in sys:
            step["n"] += 1
            if step["n"] == 1:
                return {"content": json.dumps({
                    "action": "delegate", "agent": "researcher",
                    "instruction": "Investigá la integración con el sistema propietario XYZ."}),
                    "raw": None, "tool_calls": []}
            return {"content": json.dumps({
                "action": "need_user",
                "final": "No tengo evidencia suficiente para implementar la integración con "
                         "el sistema XYZ. Intenté: búsqueda en RAG (sin resultados). "
                         "Falta: documentación oficial o specs del sistema XYZ. "
                         "Necesito: que me proporciones esa documentación o relajes el alcance."}),
                "raw": None, "tool_calls": []}
        return {"content": "[mock]", "raw": None, "tool_calls": []}

    return brain
