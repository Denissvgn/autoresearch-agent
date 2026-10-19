#!/bin/sh
# Minimal external driver: complete one attached research workflow.
#
# This program knows nothing about internal Python classes. It drives the
# autoresearch CLI's machine-readable commands and checks their stable
# exit codes. The scoped credential is referenced from the environment
# (AUTORESEARCH_AGENT_CREDENTIAL) — never passed as an argument.
set -eu

RUN_ID="${AGENT_RUN_ID:-res-external-1}"
CANDIDATE_FILE="${CANDIDATE_FILE:-$(mktemp)}"
CURSOR_FILE="${CURSOR_FILE:-$(mktemp)}"
TIMEOUT="${AGENT_TIMEOUT:-30}"

printf 'knob: 0.42\n' > "$CANDIDATE_FILE"

autoresearch() {
    python3 -m src.cli "$@"
}

# 1. create (or attach to) the run
autoresearch agent run create --instrument EURUSD --timeframe 1h

# 2. read the run's constraints
autoresearch agent constraints --run "$RUN_ID"

# 3. stage one candidate (idempotent under its key)
autoresearch agent submit \
    --run "$RUN_ID" \
    --content-file "$CANDIDATE_FILE" \
    --idempotency-key "external-1"

# 4. request evaluation (add --wait --timeout N to block for a result)
autoresearch agent evaluate --run "$RUN_ID"

# 5. inspect results (authority labels come from the service)
autoresearch agent results --run "$RUN_ID"

# 6. poll events with a persisted cursor (reconnect-safe)
autoresearch agent events --run "$RUN_ID" --cursor-file "$CURSOR_FILE"

# 7. promotion preview only — approval is an operator action
autoresearch agent preview --run "$RUN_ID"
