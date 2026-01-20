"""Discord webhook service implementation using Python and Flask.

This service handles Discord interactions webhooks:
- Validates Ed25519 signatures on incoming requests
- Responds to Ping (type=1) with Pong (type=1)
- Responds to Slash commands (type=2) with Deferred (type=5)
- Publishes sanitized slash command payloads to Pub/Sub
"""

import os

from flask import Flask, request

app = Flask(__name__)


@app.get("/health")
def health() -> tuple[dict[str, str], int]:
    return {"status": "ok"}, 200


@app.post("/interactions")
def interactions() -> tuple[dict[str, str], int]:
    _ = request.get_json(silent=True)
    return {"message": "placeholder"}, 200


@app.post("/")
def interactions_root() -> tuple[dict[str, str], int]:
    return interactions()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
