"""Summaries and paper chat through a local OpenAI-compatible server.

No model weights and no API key: a loopback server stands in for Ollama or
llama.cpp so the test stays offline.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ml.embeddings import get_embedder


def test_hash_embedder_selected_by_env(monkeypatch):
    monkeypatch.setenv("ML_EMBEDDER", "hash")
    assert get_embedder().encode(["protein folding"]).shape == (1, 384)


def test_summary_and_ask_use_local_server(service, monkeypatch):
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            seen["path"] = self.path
            seen["auth"] = self.headers.get("Authorization")
            seen["body"] = body
            system = body["messages"][0]["content"]
            text = ("Attention maps reveal contacts." if "Summarise" in system
                    else "Thresholds near one percent are observed.")
            payload = json.dumps({"choices": [{"message": {"content": text}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("ML_LLM_URL", f"http://127.0.0.1:{server.server_address[1]}/v1")
    monkeypatch.delenv("ML_LLM_API_KEY", raising=False)
    try:
        summary = service.summarize("W1")
        assert summary["method"] == "llm" and summary["summary"] == "Attention maps reveal contacts."
        assert seen["path"] == "/v1/chat/completions"
        assert seen["auth"] is None
        assert "protein" in seen["body"]["messages"][-1]["content"].lower()
        cached = service.summarize("W1")
        assert cached["cached"] is True and cached["summary"] == "Attention maps reveal contacts."
        answer = service.ask("W2", "What thresholds were observed?")
        assert answer["method"] == "llm" and "percent" in answer["answer"]
        system = seen["body"]["messages"][0]["content"]
        paper = seen["body"]["messages"][1]["content"]
        assert "Thresholds near one percent" in paper and "<abstract>" in paper
        assert "Thresholds near one percent" not in system
        assert "not instructions" in system.lower()
    finally:
        server.shutdown()
        server.server_close()
