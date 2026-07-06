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
    # A freshly-formatted volume already contains a `lost+found` directory
    # (standard ext4/xfs artifact), so a plain "is /storage empty?" check
    # (ls -A) always sees it as non-empty and skips seeding - use an
    # explicit marker file instead.
    if [ ! -e /storage/.seeded ]; then
        echo "Seeding /storage volume from image's workspace/ ..."
        cp -a /app/workspace/. /storage/
        touch /storage/.seeded
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

# Plain `su user -c cmd` (without -/-l) does NOT reset $HOME - it stays
# /root, inherited from this root shell. The bundled Claude Code CLI writes
# session state to $HOME/.claude, which appuser can't do under /root
# (permission denied), so every chat turn was failing. Set HOME explicitly.
APP_HOME="/home/$APP_USER"

echo "Running database migrations..."
su "$APP_USER" -s /bin/sh -c "export HOME=$APP_HOME; alembic upgrade head"

echo "Starting EE Finance Agent on port ${PORT:-8080}..."
exec su "$APP_USER" -s /bin/sh -c "export HOME=$APP_HOME; exec uvicorn app.main:app --host 0.0.0.0 --port \"\${PORT:-8080}\""
