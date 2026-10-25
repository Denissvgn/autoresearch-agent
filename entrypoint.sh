#!/bin/sh
# Fix ownership of volume-mounted directories that may have been created
# by a previous container with a different UID, then exec the CMD as appuser.
# Resolve appuser's UID/GID dynamically (the Dockerfile sets it via the
# APP_UID/APP_GID build args, default 1000 to match the host that owns the
# bind-mounted /host/configs) instead of hardcoding 1001 — otherwise the app
# could not write promoted configs.
set -e

APP_UID="$(id -u appuser)"
APP_GID="$(id -g appuser)"

chown -R "$APP_UID:$APP_GID" /app/workspace/runs /app/workspace/db

exec setpriv --reuid="$APP_UID" --regid="$APP_GID" --init-groups "$@"
