# Copilot Instructions

## Role
You are an expert developer working on the Discord Bot Test Suite for Cloud Run cold-start benchmarking.
You should follow the patterns and workflows defined below.

## Project Overview
This repository benchmarks Cloud Run cold-start latency across multiple language/framework implementations using a
Discord interactions webhook as the workload. It is NOT a production Discord bot—it's a test harness for measuring
webhook handling performance.

## Architecture
**Request flow:**
1. Discord interactions webhook hits the service
2. Service validates Ed25519 signature
3. For Ping (type=1): Respond with Pong, do NOT publish to Pub/Sub
4. For Slash commands (type=2): Respond with deferred (type=5), publish sanitized message to Pub/Sub

**Testing approach:** Black-box contract tests written in Go validate service behavior by making HTTP requests to
containerized services. Tests run against container images, not internal code.

**Language implementations planned:** Go/Gin, Python/Django, Python/Flask, PHP/Laravel, Ruby/Rails, C++/Drogon,
Node.js/Express, Java/Spring Boot, Rust/Actix-web, C#/ASP.NET Core

## Workflow & Issue Tracking (Beads)
This project uses **bd** (beads) for issue tracking.
- All work must go through FEATURE BRANCHES and PULL REQUESTS.
- Direct pushes to `main` are blocked.

**Quick Reference:**
```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --status in_progress  # Claim work
bd close <id>         # Complete work
bd sync               # Sync with git
```

**Session Completion:**
Work is NOT complete until `git push` succeeds.
1. File issues for remaining work
2. Run quality gates (tests, linters)
3. Update issue status (`bd close` or update)
4. Push to remote (`git pull --rebase && bd sync && git push`)

## Commands

### Contract Tests
```bash
# Run all contract tests against a service
CONTRACT_TEST_TARGET=http://localhost:8080 \
PUBSUB_EMULATOR_HOST=localhost:8085 \
go test ./tests/contract/...

# Run specific test category
go test ./tests/contract/... -run TestSignature
go test ./tests/contract/... -run TestPing
go test ./tests/contract/... -run TestSlashCommand
```

### Container Testing
```bash
docker build -t service-under-test ./services/go-gin
docker-compose -f docker-compose.test.yml up -d
go test ./tests/contract/...
docker-compose -f docker-compose.test.yml down
```

### Pub/Sub Emulator
```bash
./scripts/pubsub-emulator.sh start   # Start emulator
./scripts/pubsub-emulator.sh stop    # Stop emulator
```

## Key Constraints
- **Sensitive data redaction:** Never log `token`, `X-Signature-Ed25519`, `X-Signature-Timestamp`.
- **Pub/Sub emulator:** Use per-test unique topic/subscription names.
- **Test public key:** `DISCORD_PUBLIC_KEY=398803f0f03317b6dc57069dbe7820e5f6cf7d5ff43ad6219710b19b0b49c159`
- **Test timeout:** 30 seconds max.
- **Code Style:** Follow the patterns in existing services.
