#!/bin/sh
# Fix ownership of volume-mounted directories that may have been created
# by a previous container with a different UID (e.g. system-allocated 999).
# Runs as root briefly, then exec's the CMD as appuser (1001:1001).
set -e

chown -R 1001:1001 /app/workspace/runs /app/workspace/db

exec setpriv --reuid=1001 --regid=1001 --init-groups "$@"
