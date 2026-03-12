#!/usr/bin/env bash
set -euo pipefail

# ── Configuration ──────────────────────────────────────────────
SSH_HOST="${1:-aws-demo}"
HOST_PORT="${2:-8080}"
REMOTE_DIR="/opt/live-monitor"
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Deploying live-monitor to ${SSH_HOST}:${HOST_PORT}"

# ── 1. Prepare remote directory ───────────────────────────────
echo "==> Creating remote directories..."
ssh "$SSH_HOST" "sudo mkdir -p ${REMOTE_DIR}/{videos,data} && sudo chown -R \$(whoami):\$(whoami) ${REMOTE_DIR}"

# ── 2. Sync project files ─────────────────────────────────────
echo "==> Syncing project files..."
rsync -az --delete \
  --exclude='.git/' \
  --exclude='data/' \
  --exclude='node_modules/' \
  --exclude='frontend/dist/' \
  --exclude='.venv/' \
  --exclude='__pycache__/' \
  --exclude='.pytest_cache/' \
  --exclude='.DS_Store' \
  --exclude='.jarvis/' \
  --exclude='.idea/' \
  --exclude='.vscode/' \
  --exclude='review_output.json' \
  "$LOCAL_DIR/" "${SSH_HOST}:${REMOTE_DIR}/"

echo "==> Files synced."

# ── 3. Build and start containers ─────────────────────────────
echo "==> Building and starting containers (this may take a few minutes on first run)..."
ssh "$SSH_HOST" "cd ${REMOTE_DIR} && HOST_PORT=${HOST_PORT} docker compose up --build -d"

# ── 4. Wait for health check ──────────────────────────────────
echo "==> Waiting for backend health check..."
for i in $(seq 1 30); do
  if ssh "$SSH_HOST" "curl -sf http://localhost:${HOST_PORT}/api/health" >/dev/null 2>&1; then
    echo "==> Health check passed!"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "==> WARNING: Health check did not pass within 60s. Check logs:"
    echo "    ssh ${SSH_HOST} 'cd ${REMOTE_DIR} && docker compose logs'"
    exit 1
  fi
  sleep 2
done

# ── 5. Show status ────────────────────────────────────────────
echo ""
ssh "$SSH_HOST" "cd ${REMOTE_DIR} && docker compose ps"
echo ""

# Get the public IP
PUBLIC_IP=$(ssh "$SSH_HOST" "curl -sf http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || hostname -I | awk '{print \$1}'")

echo "=========================================="
echo "  live-monitor is running!"
echo "  http://${PUBLIC_IP}:${HOST_PORT}"
echo "=========================================="
echo ""
echo "Useful commands:"
echo "  ssh ${SSH_HOST} 'cd ${REMOTE_DIR} && docker compose logs -f'        # tail logs"
echo "  ssh ${SSH_HOST} 'cd ${REMOTE_DIR} && docker compose restart'         # restart"
echo "  ssh ${SSH_HOST} 'cd ${REMOTE_DIR} && docker compose down'            # stop"
echo "  ssh ${SSH_HOST} 'cd ${REMOTE_DIR} && HOST_PORT=${HOST_PORT} docker compose up --build -d'  # rebuild"
