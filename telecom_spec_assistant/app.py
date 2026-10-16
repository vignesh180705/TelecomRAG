from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import BadRequest

from retriever import check_configuration, retrieve_detailed

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 24 * 1024


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/status")
def status():
    missing = check_configuration()
    if missing:
        return jsonify({
            "configured": False,
            "message": "Server configuration is incomplete.",
            "missing": missing,
        }), 200
    return jsonify({
        "configured": True,
        "message": "Configuration loaded. The graph and embedding services are checked when you send a question.",
        "missing": [],
    })


@app.post("/api/chat")
def chat():
    try:
        data = request.get_json(force=True)
    except BadRequest:
        return jsonify({"error": "Please send a valid JSON request."}), 400

    question = str((data or {}).get("question", "")).strip()
    if not question:
        return jsonify({"error": "Enter a question about 3GPP or telecom specifications."}), 400
    if len(question) > 4000:
        return jsonify({"error": "Please keep your question below 4,000 characters."}), 400

    try:
        top_k = int((data or {}).get("top_k", 5))
        top_k = max(1, min(top_k, 10))
        result = retrieve_detailed(question, top_k)
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        # Keep the full exception in the server logs, not in the user's browser.
        app.logger.exception("Question retrieval failed")
        message = str(exc).strip() or "The retrieval request failed. Check the server logs."
        # Common setup errors get direct, actionable messages.
        if "Connection refused" in message and ("11434" in message or "localhost" in message):
            message = "Could not connect to Ollama. Start Ollama and ensure the nomic-embed-text model is available."
        elif "GROQ_API_KEY" in message:
            message = "The Groq API key is missing. Add GROQ_API_KEY to the server-side .env file."
        elif any(token in message for token in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE")):
            message = "Neo4j settings are missing. Check the server-side .env file."
        return jsonify({"error": message}), 500


if __name__ == "__main__":
    import os
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    app.run(host=host, port=port, debug=False)
