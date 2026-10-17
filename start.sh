#!/usr/bin/env bash
# Starts both servers in the container (Dockerfile, heroku.yml):
#   FastAPI on 127.0.0.1:8000, reachable only inside the container;
#   the Bun frontend on $PORT, which serves the pages and forwards /api to FastAPI.
# If either one exits, the other is stopped and the container exits, so Heroku restarts it.
set -euo pipefail

cd /app/Backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers &
api=$!

cd /app/Frontend
HOST=0.0.0.0 bun run .output/server/index.mjs &
web=$!

# Heroku stops a dyno with SIGTERM: pass it on to both.
trap 'kill -TERM "$api" "$web" 2>/dev/null' TERM INT

set +e
wait -n "$api" "$web"
status=$?
kill -TERM "$api" "$web" 2>/dev/null
wait
exit "$status"
