# 3GPP Specification Assistant

A local web interface for asking questions against the existing 3GPP Neo4j property graph. The UI uses the dark, muted visual style of the supplied reference screenshot, with no green success ticks or decorative chat icons. Answers show expandable retrieved source chunks and graph relationships.

## Retrieval pipeline

The server-side retriever follows the supplied Python code:

1. Embed the user question using Ollama and `nomic-embed-text`.
2. Query the Neo4j vector index named `chunk_embedding_index` for the most relevant `Chunk` records.
3. Expand the graph context through chunk-to-entity `MENTIONS` links and connected `Entity` nodes, using the configured graph depth.
4. Pass source text, source metadata, and deduplicated graph triples to the Groq-hosted model.
5. Return the answer, source metadata, similarity scores, and graph triples to the browser.

The browser never receives API keys or Neo4j credentials.

## Requirements

- Python 3.10 or newer
- Neo4j database containing the graph and vector index created by your pipeline
- Ollama running on the machine accessible to the Flask server, with `nomic-embed-text` available
- Groq API key and access to the configured model

## Setup

1. Open a terminal in this folder and create a virtual environment:

   ```bash
   python -m venv .venv
   ```

   Activate it:
   - macOS/Linux: `source .venv/bin/activate`
   - Windows: `.venv\\Scripts\\activate`

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and add your real Groq and Neo4j settings. Verify the following values match your existing graph:
   - `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`
   - `VECTOR_INDEX_NAME` (default: `chunk_embedding_index`)
   - `EMBEDDING_MODEL` (default: `nomic-embed-text`)
   - `OLLAMA_URL` (default: `http://localhost:11434/api/embed`)

4. Make sure Ollama is running and the embedding model is available:

   ```bash
   ollama pull nomic-embed-text
   ollama list
   ```

5. Start the website:

   ```bash
   python app.py
   ```

6. Open <http://127.0.0.1:5000> in your browser.

## Configuration notes

- `top_k` is selectable in the interface and is clamped to 1–10 chunks on the server.
- `GRAPH_DEPTH` is limited to 1–3. With the current query, a value of `2` expands semantic relationships up to one edge from the entities linked to each retrieved chunk, matching the logic in the original code.
- The Neo4j vector query uses the Cypher `SEARCH ... VECTOR INDEX ...` syntax from the supplied retriever. Your Neo4j version must support that syntax and the named index.
- The UI's starter questions are examples only; remove or edit them in `static/index.html` as you like.

## Troubleshooting

- **Missing server configuration**: check the `.env` file. Restart Flask after changing it.
- **Ollama connection error**: start Ollama and confirm that the configured URL is reachable from the same machine/container running Flask.
- **Neo4j connection/index error**: verify Aura credentials, database name, vector index name, and that the current database supports the vector search syntax used in `retriever.py`.
- **Groq authentication/model error**: verify the API key and model name in `.env`.
- **Slow response**: latency includes local embedding, Neo4j vector search, graph expansion, and model generation. The app keeps long-running retrieval on the server rather than the browser.

## Run on another machine

Keep Flask bound to `127.0.0.1` for local use. For a shared or public deployment, use a production WSGI server and HTTPS, add authentication and rate limiting, and restrict network access to the API. Do not expose the development server directly to the internet.
