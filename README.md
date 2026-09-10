# 3GPP LlamaIndex + Local LLM -> Neo4j

This pipeline does NOT use Grok.

Architecture:

PDFs
  -> page extraction
  -> chunks.json
  -> local LLM through LlamaIndex/Ollama
  -> extraction_raw.json
  -> validation
  -> extraction_validated.json
  -> normalization/deduplication
  -> graph_data.json
  -> Neo4j

Neo4j is only accessed by `neo4j_loader.py`.

## 1. Put PDFs here

`data/pdfs/`

Expected files:

- TS_23.501.pdf
- TS_23.502.pdf
- TS_23.503.pdf
- TS_38.300.pdf
- TS_38.304.pdf
- TS_38.306.pdf
- TR_22.870.pdf
- TR_38.914.pdf

## 2. Put your fixed schema here

Copy your validated schema to:

`schema/3gpp_schema_fixed.json`

## 3. Install dependencies

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Then:

```bash
pip install -r requirements.txt
```

## 4. Install/start Ollama

Install Ollama separately, then pull a local model.

Example:

```bash
ollama pull qwen2.5:14b
```

The model can be changed with:

```bash
set OLLAMA_MODEL=qwen2.5:14b
```

Linux/macOS:

```bash
export OLLAMA_MODEL=qwen2.5:14b
```

## 5. Create chunks

```bash
python src/main.py chunks
```

Output:

`data/chunks/chunks.json`

Inspect this file before extraction.

## 6. Extract from chunks JSON

```bash
python src/main.py extract
```

Output:

`data/extraction/extraction_raw.json`

Extraction is incremental. If a chunk is already present in the output, it is skipped.

## 7. Validate

```bash
python src/main.py validate
```

Output:

`data/extraction/extraction_validated.json`

## 8. Build final graph JSON

```bash
python src/main.py graph
```

Output:

`data/graph/graph_data.json`

Inspect this file before loading Neo4j.

## 9. Configure Neo4j

Windows:

```bash
set NEO4J_URI=bolt://localhost:7687
set NEO4J_USER=neo4j
set NEO4J_PASSWORD=your_password
```

Linux/macOS:

```bash
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=your_password
```

## 10. Load Neo4j

Only after inspecting `graph_data.json`:

```bash
python src/main.py neo4j
```

## 11. Run everything

```bash
python src/main.py all
```

The stages remain file-based even when using `all`.

## Important provenance design

Every chunk stores:

- document
- document_file
- page
- clause
- section_title
- chunk_id
- text

The extraction copies this provenance.

The graph JSON then stores provenance under `source_mentions`.

Neo4j creates `SourceMention` nodes and connects entities with:

`(:Entity)-[:MENTIONED_IN]->(:SourceMention)`

Relationship evidence is stored through:

`(entity)-[:RELATIONSHIP]->(entity)`
and
`(relationship)-[:SUPPORTED_BY]->(:RelationshipMention)`

This means an entity such as AMF can be traced back to the exact specification page/chunk that produced the extraction.

## Important limitation

Clause detection is deliberately best-effort because PDF text extraction can represent headings differently across specifications. The page number is deterministic (1-based PDF page number), while `clause` is populated only when a clause heading is visibly detected in the page text.

For production-quality clause extraction, inspect `chunks.json` and tune `CLAUSE_RE` for the exact 3GPP PDF text layout.
