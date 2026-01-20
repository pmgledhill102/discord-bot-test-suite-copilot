#!/usr/bin/env bash
#
# Run contract tests against a service implementation
#
# Usage:
#   ./scripts/run-contract-tests.sh [service-dir]
#
# Examples:
#   ./scripts/run-contract-tests.sh go-gin
#   ./scripts/run-contract-tests.sh python-flask
#
# If no service is specified, defaults to go-gin.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

SERVICE_DIR="${1:-go-gin}"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.test.yml"

echo "=============================================="
echo "Running contract tests against: $SERVICE_DIR"
echo "=============================================="
echo ""

# Check if service directory exists
if [[ ! -d "$PROJECT_ROOT/services/$SERVICE_DIR" ]]; then
  echo "ERROR: Service directory not found: services/$SERVICE_DIR"
  echo ""
  echo "Available services:"
  ls -1 "$PROJECT_ROOT/services/" 2>/dev/null || echo "  (none yet)"
  exit 1
fi

# Check if Dockerfile exists
if [[ ! -f "$PROJECT_ROOT/services/$SERVICE_DIR/Dockerfile" ]]; then
  echo "ERROR: Dockerfile not found in services/$SERVICE_DIR"
  exit 1
fi

# Export service directory for docker-compose
export SERVICE_DIR

# Clean up any previous runs
echo "Cleaning up previous test runs..."
docker-compose -f "$COMPOSE_FILE" down --remove-orphans 2>/dev/null || true

# Build and start infrastructure
echo ""
echo "Building and starting test infrastructure..."
docker-compose -f "$COMPOSE_FILE" up -d --build pubsub-emulator service-under-test

# Wait for services to be healthy
echo ""
echo "Waiting for services to be ready..."
for i in {1..60}; do
  if docker-compose -f "$COMPOSE_FILE" ps | grep -q "healthy"; then
    break
  fi
  echo "  Waiting... ($i/60)"
  sleep 2
done

# Check if services are actually healthy
if ! docker-compose -f "$COMPOSE_FILE" ps service-under-test | grep -q "healthy"; then
  echo ""
  echo "ERROR: Service failed to become healthy"
  echo ""
  echo "Service logs:"
  docker-compose -f "$COMPOSE_FILE" logs service-under-test
  docker-compose -f "$COMPOSE_FILE" down
  exit 1
fi

echo ""
echo "Services are ready. Running contract tests..."
echo ""

# Run the contract tests
docker-compose -f "$COMPOSE_FILE" run --rm contract-tests
TEST_EXIT_CODE=$?

# Cleanup
echo ""
echo "Cleaning up..."
docker-compose -f "$COMPOSE_FILE" down

# Report result
echo ""
if [[ $TEST_EXIT_CODE -eq 0 ]]; then
  echo "=============================================="
  echo "SUCCESS: All contract tests passed!"
  echo "=============================================="
else
  echo "=============================================="
  echo "FAILURE: Contract tests failed (exit code: $TEST_EXIT_CODE)"
  echo "=============================================="
fi

exit $TEST_EXIT_CODE
