# StartupGo in one container (heroku.yml): the Bun frontend on $PORT, FastAPI behind it on 127.0.0.1:8000.
# The build context is the repo root, so COPY paths start at the root (Frontend/…, Backend/…).
# The data is the committed SQLite DB; changes (e.g. research results) are lost when the container restarts.
# No Chrome: the research agent fetches pages over plain HTTP ([crawl] browser = false in Modules/Agent/config.toml)
# and needs GEMINI_API_KEY as a config var.

# Build Stage: the frontend server for Bun (preset and /api proxy in Frontend/vite.config.ts)
FROM oven/bun:1.4.3 AS frontend
WORKDIR /app/Frontend
# Only what `bun install` needs, so Docker reuses the install layer while dependencies are unchanged.
COPY Frontend/package.json Frontend/bun.lock Frontend/bunfig.toml ./
RUN bun install --frozen-lockfile
COPY Frontend/ ./
RUN bun run build

# Runtime Stage: Python for the backend, plus the Bun binary to serve the built frontend (.output only,
# so node_modules stays in the build stage).
FROM python:3.11-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
COPY --from=frontend /usr/local/bin/bun /usr/local/bin/bun

# Unbuffered logs for `heroku logs`; precompiled bytecode for a faster start; the image's Python only.
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# The backend installs Modules/Agent, Search and Scraper from these folders (editable path dependencies,
# Backend/pyproject.toml), and Agent finds Scraper through the Modules/ uv workspace, so all of it goes in
# before the install. Dependencies first, so code changes don't reinstall them.
COPY Modules/ Modules/
COPY Backend/pyproject.toml Backend/uv.lock Backend/
RUN cd Backend && uv sync --frozen --no-dev
COPY Backend/ Backend/
# The SQLite database the backend reads (Backend/app/db.py); the search index comes with Modules/Search.
COPY DB/ DB/
COPY --from=frontend /app/Frontend/.output Frontend/.output
# Starts both servers and stops the container if either one exits.
COPY start.sh ./

# Heroku sets PORT; 3000 is for running the image elsewhere.
ENV PORT=3000
EXPOSE 3000
CMD ["./start.sh"]
