"""Discord webhook service implementation using Python and Flask.

This service handles Discord interactions webhooks:
- Validates Ed25519 signatures on incoming requests
- Responds to Ping (type=1) with Pong (type=1)
- Responds to Slash commands (type=2) with Deferred (type=5)
- Publishes sanitized slash command payloads to Pub/Sub
"""

import json
import logging
import os
import time
from typing import Dict, Any, Optional

from flask import Flask, request, jsonify
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
from google.cloud import pubsub_v1

# Interaction types
INTERACTION_TYPE_PING = 1
INTERACTION_TYPE_APPLICATION_COMMAND = 2

# Response types
RESPONSE_TYPE_PONG = 1
RESPONSE_TYPE_DEFERRED_CHANNEL_MESSAGE = 5

# Initialize Flask app
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Global configuration
public_key: Optional[VerifyKey] = None
pubsub_publisher: Optional[pubsub_v1.PublisherClient] = None
pubsub_topic_path: Optional[str] = None


def init_config():
    """Initialize service configuration from environment variables."""
    global public_key, pubsub_publisher, pubsub_topic_path
    
    # Load Discord public key
    public_key_hex = os.getenv('DISCORD_PUBLIC_KEY')
    if not public_key_hex:
        raise ValueError("DISCORD_PUBLIC_KEY environment variable is required")
    
    try:
        public_key = VerifyKey(bytes.fromhex(public_key_hex))
    except Exception as e:
        raise ValueError(f"Invalid DISCORD_PUBLIC_KEY: {e}")
    
    # Initialize Pub/Sub client
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
    topic_name = os.getenv('PUBSUB_TOPIC')
    
    if project_id and topic_name:
        try:
            pubsub_publisher = pubsub_v1.PublisherClient()
            pubsub_topic_path = pubsub_publisher.topic_path(project_id, topic_name)
            
            # Ensure topic exists (for emulator, create if not exists)
            try:
                pubsub_publisher.get_topic(topic=pubsub_topic_path)
            except Exception:
                try:
                    pubsub_publisher.create_topic(name=pubsub_topic_path)
                    logger.info(f"Created Pub/Sub topic: {pubsub_topic_path}")
                except Exception as e:
                    logger.warning(f"Failed to create topic: {e}")
        except Exception as e:
            logger.warning(f"Failed to initialize Pub/Sub client: {e}")


def validate_signature(signature_hex: str, timestamp: str, body: bytes) -> bool:
    """Validate Ed25519 signature on incoming request.
    
    Args:
        signature_hex: Hex-encoded signature from X-Signature-Ed25519 header
        timestamp: Timestamp from X-Signature-Timestamp header
        body: Raw request body
        
    Returns:
        True if signature is valid, False otherwise
    """
    if not signature_hex or not timestamp:
        return False
    
    try:
        # Check timestamp (must be within 5 seconds)
        ts = int(timestamp)
        if abs(time.time() - ts) > 5:
            return False
        
        # Verify signature: sign(timestamp + body)
        message = timestamp.encode() + body
        signature = bytes.fromhex(signature_hex)
        public_key.verify(message, signature)
        return True
    except (ValueError, BadSignatureError):
        return False


def handle_ping() -> Dict[str, Any]:
    """Handle Ping interaction (type=1).
    
    Returns:
        Pong response (type=1)
    """
    return {'type': RESPONSE_TYPE_PONG}


def handle_application_command(interaction: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Application Command interaction (type=2).
    
    Publishes sanitized interaction to Pub/Sub and returns deferred response.
    
    Args:
        interaction: Parsed interaction request
        
    Returns:
        Deferred response (type=5)
    """
    # Publish to Pub/Sub in background if configured
    if pubsub_publisher and pubsub_topic_path:
        try:
            publish_to_pubsub(interaction)
        except Exception as e:
            logger.error(f"Failed to publish to Pub/Sub: {e}")
    
    # Return deferred response (non-ephemeral)
    return {'type': RESPONSE_TYPE_DEFERRED_CHANNEL_MESSAGE}


def publish_to_pubsub(interaction: Dict[str, Any]) -> None:
    """Publish sanitized interaction to Pub/Sub.
    
    Removes sensitive fields (token) before publishing.
    
    Args:
        interaction: Parsed interaction request
    """
    # Create sanitized copy (remove sensitive fields)
    sanitized = {
        'type': interaction.get('type'),
        'id': interaction.get('id'),
        'application_id': interaction.get('application_id'),
        # token is intentionally NOT copied - sensitive data
        'data': interaction.get('data'),
        'guild_id': interaction.get('guild_id'),
        'channel_id': interaction.get('channel_id'),
        'member': interaction.get('member'),
        'user': interaction.get('user'),
        'locale': interaction.get('locale'),
        'guild_locale': interaction.get('guild_locale'),
    }
    
    # Serialize to JSON
    data = json.dumps(sanitized).encode('utf-8')
    
    # Build message with attributes
    attributes = {
        'interaction_id': interaction.get('id', ''),
        'interaction_type': str(interaction.get('type', '')),
        'application_id': interaction.get('application_id', ''),
        'guild_id': interaction.get('guild_id', ''),
        'channel_id': interaction.get('channel_id', ''),
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    
    # Add command name if available
    if interaction.get('data') and 'name' in interaction['data']:
        attributes['command_name'] = interaction['data']['name']
    
    # Publish message
    future = pubsub_publisher.publish(pubsub_topic_path, data, **attributes)
    future.result(timeout=10)  # Wait for publish to complete


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok'})


@app.route('/', methods=['POST'])
@app.route('/interactions', methods=['POST'])
def handle_interaction():
    """Handle Discord interaction webhook."""
    # Get raw body
    body = request.get_data()
    
    # Validate signature
    signature = request.headers.get('X-Signature-Ed25519', '')
    timestamp = request.headers.get('X-Signature-Timestamp', '')
    
    if not validate_signature(signature, timestamp, body):
        return jsonify({'error': 'invalid signature'}), 401
    
    # Parse interaction
    try:
        interaction = request.get_json(force=True)
    except Exception:
        return jsonify({'error': 'invalid JSON'}), 400
    
    # Handle by type
    interaction_type = interaction.get('type')
    
    if interaction_type == INTERACTION_TYPE_PING:
        return jsonify(handle_ping())
    elif interaction_type == INTERACTION_TYPE_APPLICATION_COMMAND:
        return jsonify(handle_application_command(interaction))
    else:
        return jsonify({'error': 'unsupported interaction type'}), 400


if __name__ == '__main__':
    # Initialize configuration
    init_config()
    
    # Get port from environment
    port = int(os.getenv('PORT', '8080'))
    
    logger.info(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port)
