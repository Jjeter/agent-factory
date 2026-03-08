#!/usr/bin/env bash
set -euo pipefail
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "ERROR: ANTHROPIC_API_KEY is not set. Export it before running launch.sh." >&2
  exit 1
fi
docker compose build
docker compose up -d
echo "Cluster demo-date-arithmetic started. Use 'cluster tasks list' to track progress."
