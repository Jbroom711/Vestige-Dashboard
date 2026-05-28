#!/usr/bin/env bash
# start.sh — launch backend (FastAPI, :8007) + frontend (Next.js, :3007)
# for local development. Both run in one terminal; Ctrl+C stops both.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"

# ----- preflight checks -----------------------------------------------------
check_port() {
    local port=$1 name=$2
    if lsof -i ":$port" -P -n -sTCP:LISTEN >/dev/null 2>&1; then
        echo "❌ Port $port is already in use (needed for $name)."
        echo "   Run:  lsof -i :$port    to see what's using it, then kill it."
        return 1
    fi
}
check_port 8007 "backend" || exit 1
check_port 3007 "frontend" || exit 1

if [ ! -x "$BACKEND_DIR/.venv/bin/uvicorn" ]; then
    echo "❌ Backend venv missing or uvicorn not installed."
    echo "   First-time setup:"
    echo "     cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "❌ Frontend node_modules missing."
    echo "   First-time setup:  cd frontend && npm install"
    exit 1
fi

# ----- start backend in background -----------------------------------------
echo "▶ Starting backend on http://localhost:8007 ..."
(
    cd "$BACKEND_DIR"
    .venv/bin/uvicorn app.main:app --reload --port 8007 2>&1 | sed 's/^/[backend] /'
) &
BACKEND_PID=$!

# Give uvicorn ~1s to bind the port; bail early if it died on boot
sleep 1
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "❌ Backend process died on startup. Check the [backend] output above."
    exit 1
fi

# ----- cleanup on exit -----------------------------------------------------
cleanup() {
    echo
    echo "▶ Stopping backend..."
    # uvicorn --reload spawns a worker child; kill the group
    pkill -P "$BACKEND_PID" 2>/dev/null || true
    kill "$BACKEND_PID" 2>/dev/null || true
    sleep 0.3
    # Belt-and-suspenders: anything still bound to :8007 gets evicted
    lsof -ti :8007 | xargs kill -9 2>/dev/null || true
    echo "✓ Stopped."
}
trap cleanup EXIT INT TERM

# ----- start frontend in foreground ----------------------------------------
echo "▶ Starting frontend on http://localhost:3007 ..."
echo "  Both servers running. Press Ctrl+C to stop both."
echo
cd "$FRONTEND_DIR"
npm run dev 2>&1 | sed 's/^/[frontend] /'
