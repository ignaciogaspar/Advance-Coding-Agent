#!/usr/bin/env bash
# Corre la suite completa del TP con APIs reales (Gemini + Langfuse).
# Uso:  bash run_all_demos.sh
set -e
cd "$(dirname "$0")"

# Crear/usar un entorno virtual del proyecto (evita el error
# "externally-managed-environment" del Python de Homebrew).
if [ ! -d ".venv" ]; then
  echo "==> Creando entorno virtual .venv ..."
  python3 -m venv .venv
fi
PY=".venv/bin/python"
echo "Usando: $PY ($($PY --version))"

echo "==> 1/6 Instalando dependencias..."
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -r requirements.txt pytest

echo "==> 2/6 Tests offline (pytest)..."
"$PY" -m pytest -q tests/test_offline.py

echo "==> 3/6 Ingest RAG con embeddings reales..."
"$PY" -m advanced_agent.rag.ingest

echo "==> 4/6 Demo 1 (RAG) y Demo 2 (memoria)..."
"$PY" tests/demo_1_rag.py
"$PY" tests/demo_2_memory.py

echo "==> 5/6 Demo 3 (bloqueo / pedir ayuda)..."
"$PY" tests/demo_3_block.py

echo "==> 6/6 Demo 4 (observabilidad -> Langfuse)..."
"$PY" tests/demo_4_observability.py

echo ""
echo "LISTO. Abrí https://us.cloud.langfuse.com -> Traces y sacá las capturas:"
echo "  (a) lista de traces   (b) detalle de una traza (árbol de spans)"
echo "  (c) detalle de una generación LLM (modelo, tokens, latencia)"
echo "Guardalas en docs/screenshots/"
