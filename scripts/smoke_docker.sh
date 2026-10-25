#!/usr/bin/env bash
# Scripted Docker smoke test.
#
# The repeatable version of the by-hand image check: build the image, run it
# detached, assert readiness + the installed skills, start a REAL
# prompt-engineering demo session through the public API, assert it reaches
# a recorded iteration, then tear down. Non-zero exit on any failure.
#
# It exercises exactly the path a real operator hits — nothing is mocked
# inside the container.
#
# Usage:
#   scripts/smoke_docker.sh                 # build + smoke
#   SKIP_BUILD=1 scripts/smoke_docker.sh    # reuse an existing image
#   IMAGE=myrepo/agent:tag scripts/smoke_docker.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${IMAGE:-autoresearch-agent:smoke}"
CONTAINER="${CONTAINER:-ar-smoke-$$}"
PORT="${PORT:-18030}"
API="http://127.0.0.1:${PORT}"
TOKEN="demo-token"
READY_TIMEOUT_S="${READY_TIMEOUT_S:-120}"
SESSION_TIMEOUT_S="${SESSION_TIMEOUT_S:-180}"

log() { printf '[smoke] %s\n' "$*"; }
fail() { printf '[smoke] FAIL: %s\n' "$*" >&2; exit 1; }

cleanup() {
  log "tearing down ${CONTAINER}"
  docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# ── 1. Build ────────────────────────────────────────────────────────────────
if [ "${SKIP_BUILD:-0}" != "1" ]; then
  log "building image ${IMAGE}"
  docker build -t "${IMAGE}" "${REPO_ROOT}" >/dev/null || fail "docker build failed"
else
  log "skipping build (SKIP_BUILD=1)"
fi

# ── 2. Run detached (demo mode, SQLite — no external dependencies) ──────────
log "running ${CONTAINER} on 127.0.0.1:${PORT}"
docker run -d --name "${CONTAINER}" \
  -p "127.0.0.1:${PORT}:8000" \
  -e AUTORESEARCH_DEMO=true \
  -e AUTORESEARCH_EXECUTION_ISOLATION_MODE=trusted_local_code \
  -e AUTORESEARCH_API_TOKEN="${TOKEN}" \
  -e AUTORESEARCH_DATABASE_URL= \
  "${IMAGE}" >/dev/null || fail "docker run failed"

# ── 3. Readiness ────────────────────────────────────────────────────────────
log "polling /health and /health/ready (timeout ${READY_TIMEOUT_S}s)"
deadline=$(( $(date +%s) + READY_TIMEOUT_S ))
while [ "$(date +%s)" -lt "${deadline}" ]; do
  if curl -fsS "${API}/health" >/dev/null 2>&1 \
     && curl -fsS "${API}/health/ready" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS "${API}/health" >/dev/null || fail "/health never became ready"
curl -fsS "${API}/health/ready" >/dev/null || fail "/health/ready never became ready"
log "service is ready"

# ── 4. Installed skills ─────────────────────────────────────────────────────
auth_header="Authorization: Bearer ${TOKEN}"
skills_json="$(curl -fsS -H "${auth_header}" "${API}/api/v1/skills")" \
  || fail "GET /api/v1/skills failed"
for skill in prompt-engineering code-refactor db-config-tuning; do
  printf '%s' "${skills_json}" | grep -q "\"${skill}\"" \
    || fail "skill ${skill} missing from /api/v1/skills"
done
log "all 3 bundled skills listed"

# ── 5. A REAL demo session reaching an iteration ────────────────────────────
log "starting a prompt-engineering demo session"
start_body="$(curl -fsS -X POST "${API}/api/v1/research/start" \
  -H "${auth_header}" -H 'Content-Type: application/json' \
  -d '{"skill_id":"prompt-engineering","max_iterations":1}')" \
  || fail "POST /research/start failed (see docker logs ${CONTAINER})"
research_id="$(printf '%s' "${start_body}" | sed -n 's/.*"id"[[:space:]]*:[[:space:]]*"\(res_[^"]*\)".*/\1/p')"
[ -n "${research_id}" ] || fail "could not parse session id from: ${start_body}"
log "session ${research_id} started; polling for a recorded iteration"

deadline=$(( $(date +%s) + SESSION_TIMEOUT_S ))
status=""
while [ "$(date +%s)" -lt "${deadline}" ]; do
  session_json="$(curl -fsS -H "${auth_header}" "${API}/api/v1/research/${research_id}")"
  status="$(printf '%s' "${session_json}" | sed -n 's/.*"status"[[:space:]]*:[[:space:]]*"\([a-z_]*\)".*/\1/p' | head -1)"
  iterations="$(curl -fsS -H "${auth_header}" "${API}/api/v1/research/${research_id}/iterations")"
  if printf '%s' "${iterations}" | grep -q '"primary_metric"'; then
    log "iteration recorded (status=${status:-unknown})"
    break
  fi
  case "${status}" in
    failed|timed_out)
      fail "session ${research_id} reached ${status} without an iteration: ${session_json}"
      ;;
  esac
  sleep 2
done
printf '%s' "${iterations}" | grep -q '"primary_metric"' \
  || fail "no iteration recorded within ${SESSION_TIMEOUT_S}s (last status: ${status:-unknown}; docker logs ${CONTAINER})"

# ── 6. The session must reach a clean terminal state ───────────────────────
deadline=$(( $(date +%s) + 60 ))
while [ "$(date +%s)" -lt "${deadline}" ]; do
  session_json="$(curl -fsS -H "${auth_header}" "${API}/api/v1/research/${research_id}")"
  status="$(printf '%s' "${session_json}" | sed -n 's/.*"status"[[:space:]]*:[[:space:]]*"\([a-z_]*\)".*/\1/p' | head -1)"
  case "${status}" in
    completed|stopped) break ;;
    failed|timed_out) fail "session ${research_id} ended as ${status}: ${session_json}" ;;
  esac
  sleep 2
done
case "${status}" in
  completed|stopped) log "session ${research_id} finished: ${status}" ;;
  *) fail "session ${research_id} did not reach a terminal state (status=${status:-unknown})" ;;
esac

log "SMOKE OK — image serves readiness, skills, and a real non-ML session end to end"
