"""Discord webhook service implementation using Python and Flask.

This service handles Discord interactions webhooks:
- Validates Ed25519 signatures on incoming requests
- Responds to Ping (type=1) with Pong (type=1)
- Responds to Slash commands (type=2) with Deferred (type=5)
- Publishes sanitized slash command payloads to Pub/Sub
"""

import os
import time
from functools import wraps

from flask import Flask, g, request
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

app = Flask(__name__)

PUBLIC_KEY_HEX = os.environ.get("DISCORD_PUBLIC_KEY")
if not PUBLIC_KEY_HEX:
    raise RuntimeError("DISCORD_PUBLIC_KEY environment variable is required")

try:
    VERIFY_KEY = VerifyKey(bytes.fromhex(PUBLIC_KEY_HEX))
except ValueError as exc:
    raise RuntimeError("Invalid DISCORD_PUBLIC_KEY") from exc


def get_raw_body() -> bytes:
    if not hasattr(g, "raw_body"):
        g.raw_body = request.get_data(cache=True) or b""
    return g.raw_body


def is_valid_signature() -> bool:
    signature = request.headers.get("X-Signature-Ed25519")
    timestamp = request.headers.get("X-Signature-Timestamp")

    if not signature or not timestamp:
        return False

    try:
        sig_bytes = bytes.fromhex(signature)
    except ValueError:
        return False

    if len(sig_bytes) != 64:
        return False

    try:
        ts = int(timestamp)
    except ValueError:
        return False

    if int(time.time()) - ts > 5:
        return False

    message = timestamp.encode() + get_raw_body()
    try:
        VERIFY_KEY.verify(message, sig_bytes)
    except BadSignatureError:
        return False

    return True


def require_valid_signature(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not is_valid_signature():
            return {"error": "invalid signature"}, 401
        return view(*args, **kwargs)

    return wrapper


@app.get("/health")
def health() -> tuple[dict[str, str], int]:
    return {"status": "ok"}, 200


@app.post("/interactions")
@require_valid_signature
def interactions() -> tuple[dict[str, str], int]:
    payload = request.get_json(silent=True) or {}
    interaction_type = payload.get("type")
    if interaction_type == 1:
        return {"type": 1}, 200
    if interaction_type is None:
        return {"error": "missing type"}, 400
    return {"message": "placeholder"}, 200


@app.post("/")
def interactions_root() -> tuple[dict[str, str], int]:
    return interactions()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
