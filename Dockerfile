# ---- Build stage: compile any Python deps that need a C toolchain ----
FROM python:3.14-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libffi-dev \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Runtime stage ----
FROM python:3.14-slim

WORKDIR /app

# git + gh: Builder-mode chat sessions run `git`/`gh` via the agent's Bash tool
# to publish generated commission rule modules to GitHub.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
        gnupg \
    && mkdir -p -m 755 /etc/apt/keyrings \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends gh \
    && apt-get purge -y gnupg \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY . .

# workspace/ (uploads, documents, specs, decisions, memory, DB_SCHEMA.md) is
# written to at runtime and must persist across redeploys. Production's
# Railway volume is mounted at /storage; docker-entrypoint.sh symlinks
# /app/workspace -> /storage at boot. rules/ (Builder-mode generated code) is
# not persisted this way - it's expected to be pushed to GitHub instead.
RUN mkdir -p workspace/uploads workspace/documents workspace/decisions workspace/specs workspace/memory rules

# The bundled Claude Code CLI (spawned by claude_agent_sdk) refuses to run
# with permission_mode="bypassPermissions" (--dangerously-skip-permissions)
# as root, for its own safety reasons - so the app must run as a non-root
# user. docker-entrypoint.sh still starts as root (the container's default
# user) to fix up ownership of the mounted volume, then drops to this user
# via `su` before running migrations/starting the server.
RUN useradd --create-home --uid 10001 appuser

EXPOSE 8080

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
