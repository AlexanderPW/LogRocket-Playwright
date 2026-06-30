#!/usr/bin/env bash
# Run the web dashboard (API + Next.js frontend)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

source .venv/bin/activate
pip install -e ".[web]" -q

trap 'kill 0' EXIT
e2e-api --reload &
API_PID=$!

cd frontend
npm install --silent 2>/dev/null || npm install
PORT=3001 npm run dev &
WEB_PID=$!

echo ""
echo "  API:       http://localhost:8001"
echo "  Dashboard: http://localhost:3001"
echo ""

wait $API_PID $WEB_PID
