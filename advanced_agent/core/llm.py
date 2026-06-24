"""Cliente LLM con tracing integrado.

Envuelve la API de OpenAI (chat + embeddings) e instrumenta cada llamada con
el Tracer (tokens, latencia, costo). Soporta un modo "mock" para correr el
sistema sin red ni claves (útil en CI y para las pruebas offline).
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Callable

from .observability import Tracer


def _approx_tokens(text: str) -> int:
    """Estimación barata de tokens (~4 chars/token) si no hay tiktoken."""
    return max(1, len(text) // 4)


class LLMClient:
    def __init__(self, chat_model: str, embed_model: str, tracer: Tracer,
                 mock: bool | None = None, mock_handler: Callable | None = None):
        self.chat_model = chat_model
        self.embed_model = embed_model
        self.tracer = tracer
        # Modo mock automático si no hay clave (a menos que se fuerce).
        self.mock = mock if mock is not None else not os.environ.get("OPENAI_API_KEY")
        self.mock_handler = mock_handler
        self._client = None

    def _openai(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        return self._client

    # ---------------- chat ----------------
    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             temperature: float = 0.2) -> dict:
        """Devuelve un dict normalizado: {content, tool_calls, raw}.

        tool_calls es una lista de {id, name, arguments(dict)}.
        """
        start = time.time()
        prompt_preview = json.dumps(messages, ensure_ascii=False)[-1500:]

        if self.mock:
            out = self._mock_chat(messages, tools)
            latency = round(time.time() - start, 4)
            self.tracer.log_llm(self.chat_model + "[mock]", prompt_preview,
                                _approx_tokens(prompt_preview),
                                _approx_tokens(out.get("content") or ""),
                                latency, out.get("content") or "")
            return out

        kwargs: dict[str, Any] = {"model": self.chat_model, "messages": messages,
                                  "temperature": temperature}
        if tools:
            kwargs["tools"] = tools
        resp = self._openai().chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        latency = round(time.time() - start, 4)

        tool_calls = []
        for tc in (msg.tool_calls or []):
            try:
                args = json.loads(tc.function.arguments)
            except Exception:  # noqa: BLE001
                args = {}
            tool_calls.append({"id": tc.id, "name": tc.function.name, "arguments": args})

        usage = getattr(resp, "usage", None)
        in_tok = getattr(usage, "prompt_tokens", _approx_tokens(prompt_preview))
        out_tok = getattr(usage, "completion_tokens", _approx_tokens(msg.content or ""))
        self.tracer.log_llm(self.chat_model, prompt_preview, in_tok, out_tok,
                            latency, msg.content or "")
        return {"content": msg.content, "tool_calls": tool_calls, "raw": msg}

    # ---------------- embeddings ----------------
    def embed(self, texts: list[str]) -> list[list[float]]:
        start = time.time()
        if self.mock:
            vecs = [self._mock_embed(t) for t in texts]
            self.tracer.log_llm(self.embed_model + "[mock]", f"{len(texts)} texts",
                                sum(_approx_tokens(t) for t in texts), 0,
                                round(time.time() - start, 4))
            return vecs
        resp = self._openai().embeddings.create(model=self.embed_model, input=texts)
        self.tracer.log_llm(self.embed_model, f"{len(texts)} texts",
                            getattr(resp, "usage", None) and resp.usage.total_tokens
                            or sum(_approx_tokens(t) for t in texts), 0,
                            round(time.time() - start, 4))
        return [d.embedding for d in resp.data]

    # ---------------- mocks deterministas ----------------
    def _mock_chat(self, messages: list[dict], tools: list[dict] | None) -> dict:
        if self.mock_handler:
            return self.mock_handler(messages, tools)
        return {"content": "[mock] respuesta de prueba.", "tool_calls": [], "raw": None}

    @staticmethod
    def _mock_embed(text: str, dim: int = 256) -> list[float]:
        """Embedding determinista basado en hashing de tokens (bag-of-words).

        No es semántico como OpenAI, pero permite probar el pipeline RAG
        (chunking, store, retrieval, ranking) sin red. Palabras compartidas
        producen vectores más cercanos."""
        import hashlib
        import math
        vec = [0.0] * dim
        for tok in text.lower().split():
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            vec[h % dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]
