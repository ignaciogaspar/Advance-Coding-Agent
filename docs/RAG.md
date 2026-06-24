# Base RAG — documentación

El agente se especializa en **FastAPI**. El RAG le da conocimiento de la
documentación oficial sin tener que mandarla entera al modelo.

## Fuentes

Corpus en `rag_corpus/` (6 documentos + `SOURCES.md`), derivado de la
documentación oficial de FastAPI (repo `fastapi/fastapi`, `docs/en/docs`):

| Archivo | Tema |
|---------|------|
| `01_first_steps.md` | App mínima, path operations, OpenAPI |
| `02_request_body_pydantic.md` | Request body con modelos Pydantic |
| `03_dependencies.md` | Inyección de dependencias (`Depends`) |
| `04_response_model.md` | `response_model`, filtrado de salida |
| `05_testing_and_errors.md` | `TestClient`, `HTTPException`, status codes |
| `06_project_structure_routers.md` | `APIRouter`, estructura de proyecto |

Para ampliar el corpus, agregá `.md/.txt/.rst/.py` a `rag_corpus/` y reindexá.

## Pipeline (`advanced_agent/rag/`)

### 1. Chunking — `index.py::chunk_text`

Divide cada documento en chunks de `chunk_size` caracteres (800 por defecto) con
`overlap` de solape (150). Intenta cortar en límites de párrafo (`\n\n`), línea
(`\n`) u oración (`. `) para no partir ideas. Cada chunk lleva un `id`
(`archivo#n`) y su `source`.

### 2. Embeddings — `core/llm.py::LLMClient.embed`

Usa OpenAI `text-embedding-3-small`. Sin `OPENAI_API_KEY`, usa un **embedding
mock determinista** (bag-of-words con hashing) que permite probar todo el
pipeline (chunking → store → ranking) sin red. Los embeddings se calculan por
lotes (batch de 64).

### 3. Almacenamiento vectorial — `index.py::RagIndex.build`

Persiste un único JSON `data/rag_index.json` con `meta` (nº de archivos, chunks,
modelo, tamaños) y `docs` (cada chunk con su `embedding`). No se usa ninguna base
vectorial externa: es transparente y suficiente para el tamaño del corpus.

### 4. Recuperación — `index.py::RagIndex.search`

Embebe la consulta y calcula **similitud coseno** (numpy) contra todos los
chunks; devuelve los `top_k` con su `score`. La tool `rag_search`
(`tools/plugins/rag.py`):

- Muestra los **documentos recuperados, sus scores y los fragmentos citados**.
- Marca la evidencia como **suficiente o débil** según `min_score`.
- Registra cada fragmento en el estado como **origen `rag`**, distinguiéndolo de
  `repo`, `memory`, `web` e `inference`.

## Política de búsqueda (RAG-first)

El `ResearcherAgent` tiene la regla en su system prompt y en el código de la tool:

1. **Siempre** consultar primero `rag_search`.
2. **Sólo** si la evidencia del RAG es insuficiente (score < `min_score`), usar
   `web_search`, priorizando documentación oficial y fuentes técnicas confiables.

## Construir / reconstruir el índice

```bash
python -m advanced_agent.rag.ingest          # con OPENAI_API_KEY (embeddings reales)
python -m advanced_agent.rag.ingest --mock   # sin clave (embeddings mock)
```

Salida típica (mock): `n_files: 7, n_chunks: 28, embed_model: text-embedding-3-small`.

> Nota: los embeddings mock **no son semánticos**, así que el ranking en modo mock
> es aproximado (sirve para verificar el pipeline). Con embeddings reales de
> OpenAI, los documentos relevantes rankean correctamente arriba.
