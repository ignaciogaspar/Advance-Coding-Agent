"""RAG: chunking, embeddings, almacenamiento vectorial y recuperación.

Sin frameworks de orquestación ni bases vectoriales externas: el vector store
es un archivo JSON con los vectores y, en recuperación, se calcula la
similitud coseno con numpy. Suficiente y transparente para el corpus de docs.

Componentes:
  - chunk_text()   : chunking por caracteres con solape.
  - RagIndex.build : embebe cada chunk y persiste el índice.
  - RagIndex.search: embebe la consulta y devuelve los top_k por coseno.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None


def chunk_text(text: str, source: str, chunk_size: int = 800,
               overlap: int = 150) -> list[dict]:
    """Divide el texto en chunks solapados, intentando cortar en límites de
    párrafo/oración para no partir ideas a la mitad."""
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    n = len(text)
    idx = 0
    while start < n:
        end = min(start + chunk_size, n)
        # Intentar terminar en un salto de párrafo o punto cercano.
        if end < n:
            window = text[start:end]
            for sep in ("\n\n", "\n", ". "):
                pos = window.rfind(sep)
                if pos > chunk_size * 0.5:
                    end = start + pos + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append({"id": f"{source}#{idx}", "source": source, "text": chunk})
            idx += 1
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


def _cosine(a: list[float], b: list[float]) -> float:
    if np is not None:
        va, vb = np.asarray(a), np.asarray(b)
        denom = (np.linalg.norm(va) * np.linalg.norm(vb)) or 1.0
        return float(va.dot(vb) / denom)
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


@dataclass
class RagIndex:
    index_path: Path
    llm: object                       # LLMClient (provee embed())
    chunk_size: int = 800
    overlap: int = 150
    _docs: list[dict] | None = None   # cache en memoria

    # ---------------- construcción ----------------
    def build(self, corpus_dir: str | Path,
              exts=(".md", ".txt", ".rst", ".py")) -> dict:
        """Lee el corpus, hace chunking, embebe y persiste el índice."""
        corpus_dir = Path(corpus_dir)
        files = [p for p in corpus_dir.rglob("*") if p.suffix in exts and p.is_file()]
        all_chunks: list[dict] = []
        for fp in sorted(files):
            try:
                text = fp.read_text(encoding="utf-8", errors="ignore")
            except Exception:  # noqa: BLE001
                continue
            rel = str(fp.relative_to(corpus_dir))
            all_chunks.extend(chunk_text(text, rel, self.chunk_size, self.overlap))

        if not all_chunks:
            raise RuntimeError(f"No se encontraron documentos en {corpus_dir}")

        # Embeddings por lotes.
        texts = [c["text"] for c in all_chunks]
        vectors = []
        BATCH = 64
        for i in range(0, len(texts), BATCH):
            vectors.extend(self.llm.embed(texts[i:i + BATCH]))
        for c, v in zip(all_chunks, vectors):
            c["embedding"] = v

        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        meta = {"n_files": len(files), "n_chunks": len(all_chunks),
                "embed_model": getattr(self.llm, "embed_model", "?"),
                "chunk_size": self.chunk_size, "overlap": self.overlap}
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump({"meta": meta, "docs": all_chunks}, f, ensure_ascii=False)
        self._docs = all_chunks
        return meta

    # ---------------- carga / consulta ----------------
    def _load(self) -> list[dict]:
        if self._docs is not None:
            return self._docs
        if not self.index_path.exists():
            self._docs = []
            return self._docs
        with open(self.index_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._docs = data.get("docs", [])
        return self._docs

    def ready(self) -> bool:
        return len(self._load()) > 0

    def meta(self) -> dict:
        if not self.index_path.exists():
            return {}
        with open(self.index_path, "r", encoding="utf-8") as f:
            return json.load(f).get("meta", {})

    def search(self, query: str, top_k: int = 4) -> list[dict]:
        """Devuelve los top_k chunks por similitud coseno (sin el embedding)."""
        docs = self._load()
        if not docs:
            return []
        qv = self.llm.embed([query])[0]
        scored = []
        for d in docs:
            emb = d.get("embedding")
            if not emb:
                continue
            scored.append((_cosine(qv, emb), d))
        scored.sort(key=lambda t: t[0], reverse=True)
        out = []
        for score, d in scored[:top_k]:
            out.append({"id": d["id"], "source": d["source"],
                        "text": d["text"], "score": round(score, 4)})
        return out
