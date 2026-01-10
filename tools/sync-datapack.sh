#!/usr/bin/env bash
set -euo pipefail

# Load .env and .env.local if present (simple dotenv support without dependencies).
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  . .env
  set +a
fi
if [[ -f .env.local ]]; then
  set -a
  # shellcheck disable=SC1091
  . .env.local
  set +a
fi

if [[ -z "${MC_DIR:-}" || -z "${WORLD_NAME:-}" || -z "${DATAPACK_NAME:-}" ]]; then
  echo "Missing env vars. Set MC_DIR, WORLD_NAME, DATAPACK_NAME in .env"
  exit 1
fi

SRC_DIR="datapack"
DEST_DIR="${MC_DIR}/saves/${WORLD_NAME}/datapacks/${DATAPACK_NAME}"

if [[ ! -d "${MC_DIR}/saves/${WORLD_NAME}" ]]; then
  echo "World not found: ${MC_DIR}/saves/${WORLD_NAME}"
  exit 1
fi

mkdir -p "${DEST_DIR}"

rsync -av --delete \
  --exclude ".gitkeep" \
  "${SRC_DIR}/" "${DEST_DIR}/"

echo "Synced ${SRC_DIR} -> ${DEST_DIR}"
