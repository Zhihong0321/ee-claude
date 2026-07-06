#!/bin/sh
set -e

APP_USER=appuser
APP_UID=10001

# The app hardcodes paths under ./workspace (uploads, documents, specs,
# decisions, memory, DB_SCHEMA.md). Production's persistent volume is
# mounted at /storage, so redirect workspace/ there via a symlink rather
# than changing every path in the app. Runs on every boot since each
# deploy starts from a fresh image (workspace/ exists as a real directory
# again, seeded from git) - only /storage survives across deploys.
if [ -d /storage ] && [ ! -L /app/workspace ]; then
    if [ -z "$(ls -A /storage 2>/dev/null)" ]; then
        echo "Seeding empty /storage volume from image's workspace/ ..."
        cp -a /app/workspace/. /storage/
    fi
    rm -rf /app/workspace
    ln -s /storage /app/workspace
fi

# Container starts as root (default). The app itself must run as a
# non-root user (the bundled Claude Code CLI refuses --dangerously-skip-
# permissions as root), so hand ownership of everything it needs to write
# to over to appuser, then drop privileges for the actual process.
[ -d /storage ] && chown -R "$APP_UID:$APP_UID" /storage
chown -R "$APP_UID:$APP_UID" /app

echo "Running database migrations..."
su "$APP_USER" -s /bin/sh -c "alembic upgrade head"

echo "Starting EE Finance Agent on port ${PORT:-8080}..."
exec su "$APP_USER" -s /bin/sh -c "exec uvicorn app.main:app --host 0.0.0.0 --port \"\${PORT:-8080}\""
