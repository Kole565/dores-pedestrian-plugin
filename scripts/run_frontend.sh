#!/usr/bin/env bash
# scripts/run_frontend.sh — dev-сервер Vite
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT/frontend"

if [[ ! -d node_modules ]]; then
  echo "[INFO] Устанавливаем зависимости frontend…"
  npm install
fi

exec npm run dev
