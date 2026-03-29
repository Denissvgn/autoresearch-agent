#!/bin/sh
# Fix ownership of volume-mounted directories that may have been created
# by a previous container with a different UID (e.g. system-allocated 999).
# Runs as root briefly, then exec's the CMD as appuser (1000:1000).
set -e

chown -R 1000:1000 /app/workspace/runs /app/workspace/db 2>/dev/null || true

exec setpriv --reuid=1000 --regid=1000 --init-groups "$@"
