# TelecomRAG — Source-Grounded Property Graph Pipeline

## Pipeline

PDFs -> chunks -> canonical entities -> source-grounded relationships -> validation/deduplication -> Neo4j

The LLM never creates new entity IDs. It only extracts relationships between canonical entities that are mentioned in the source chunk. Every retained relationship requires verbatim evidence from the chunk and must satisfy the ontology source/target type constraints.

## Setup

```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# Linux/macOS
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # Windows
# cp .env.example .env   # Linux/macOS
```

Put source PDFs in `data/pdfs/` and the canonical entity registry in `output/entity_registry_v4_canonical.json`.

## Run

```bash
python src/chunk_documents.py
python src/build_relationship_registry.py --limit-chunks 100
python src/build_relationship_registry.py
python src/build_graph.py
python src/validate_graph.py
```

Start with `--limit-chunks 50` or `100` to inspect extraction quality before processing the whole corpus.

## Neo4j model

- `(:Entity)` stores canonical entities; `entity_type` stores the ontology type.
- `(:Document)` stores source documents.
- `(:Chunk)` stores source evidence chunks.
- Ontology relationship types are stored as Neo4j relationship types.
- `SUPPORTED_BY` and `MENTIONED_IN` connect graph entities to evidence chunks.

## Important

Do not commit `.env` or API credentials. Do not treat the generated relationship registry as final until it has been manually sampled and validated.
