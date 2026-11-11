#!/usr/bin/env bash
# reset.sh - recover burrows from tampering (deleted flag, killed service,
# patched vuln) WITHOUT rotating flags and WITHOUT touching the scoreboard.
set -euo pipefail

cd "$(dirname "$0")/.."

# Every compose service except the scoreboard is a burrow target.
BURROW_SERVICES="$(docker compose config --services | grep -v '^scoreboard$' || true)"

if [[ -z "$BURROW_SERVICES" ]]; then
  echo "no burrow services found; nothing to reset" >&2
  exit 0
fi

# shellcheck disable=SC2086
docker compose up -d --build --force-recreate $BURROW_SERVICES

echo "reset burrows: $(echo "$BURROW_SERVICES" | tr '\n' ' ')"
