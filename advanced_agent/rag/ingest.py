"""Script de ingest del corpus RAG.

Uso:
    python -m advanced_agent.rag.ingest [--corpus rag_corpus] [--config agent.config.yaml]

Lee los documentos del corpus, los divide en chunks, calcula embeddings (OpenAI
o mock si no hay clave) y persiste el índice vectorial en data/rag_index.json.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from ..core.config import load_config
from ..core.llm import LLMClient
from ..core.observability import Tracer
from .index import RagIndex


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingesta del corpus RAG.")
    ap.add_argument("--corpus", default="rag_corpus", help="Carpeta del corpus.")
    ap.add_argument("--config", default="agent.config.yaml")
    ap.add_argument("--mock", action="store_true",
                    help="Forzar embeddings mock (sin red ni clave).")
    args = ap.parse_args()

    cfg = load_config(args.config)
    tracer = Tracer(cfg.observability, run_name="rag-ingest")
    llm = LLMClient(cfg.chat_model, cfg.embed_model, tracer,
                    mock=True if args.mock else None)

    rag_cfg = cfg.rag
    index = RagIndex(
        index_path=cfg.resolve(rag_cfg.get("index_path", "./data/rag_index.json")),
        llm=llm,
        chunk_size=rag_cfg.get("chunk_size", 800),
        overlap=rag_cfg.get("chunk_overlap", 150),
    )

    corpus_dir = Path(args.corpus)
    if not corpus_dir.is_absolute():
        corpus_dir = (Path(args.config).resolve().parent / corpus_dir)

    print(f"Indexando corpus: {corpus_dir}")
    meta = index.build(corpus_dir)
    print("Índice construido:")
    for k, v in meta.items():
        print(f"  {k}: {v}")
    print(f"Guardado en: {index.index_path}")
    if llm.mock:
        print("\n[AVISO] Se usaron embeddings MOCK (no semánticos). Para producción, "
              "exportá OPENAI_API_KEY y re-ejecutá sin --mock.")


if __name__ == "__main__":
    main()
