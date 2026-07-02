#!/bin/bash
set -euo pipefail

LOGFILE="/opt/zheye/logs/post_pull_$(date +%Y%m%d_%H%M%S).log"
mkdir -p /opt/zheye/logs

exec > >(tee -a "$LOGFILE") 2>&1

echo "=== Post-Pull Setup Script Started at $(date) ==="

echo "[1/6] Waiting 1 hour (3600 seconds)..."
sleep 3600
echo "[1/6] Wait completed at $(date)"

echo "[2/6] Running git pull..."
cd /opt/zheye
git stash 2>/dev/null || true
CHANGES=$(git pull origin main 2>&1)
echo "$CHANGES"

if echo "$CHANGES" | grep -q "Already up to date"; then
    echo "No new changes. Exiting."
    exit 0
fi

echo "[3/6] Checking for new requirements..."
if git diff HEAD~1 --name-only | grep -q "requirements"; then
    echo "Installing updated dependencies..."
    /opt/zheye/venv/bin/pip install -r requirements.txt 2>&1
fi

echo "[4/6] Checking for new migrations..."
NEW_MIGRATIONS=$(git diff HEAD~1 --name-only | grep "migrations/" || true)
if [ -n "$NEW_MIGRATIONS" ]; then
    echo "New migrations found: $NEW_MIGRATIONS"
    for mig in $NEW_MIGRATIONS; do
        if [[ "$mig" == *.sql ]]; then
            echo "Applying migration: $mig"
            PGPASSWORD=XHVndrfT07TC4y psql -h localhost -U zheye -d zheye -f "$mig" 2>&1 || echo "Warning: Migration $mig may have already been applied"
        fi
    done
fi

echo "[5/6] Checking for new .env variables..."
if git diff HEAD~1 --name-only | grep -q ".env.example"; then
    echo "New .env.example detected. Comparing..."
    diff .env.example .env 2>/dev/null || true
fi

echo "[6/6] Restarting zheye service..."
sudo systemctl restart zheye
sleep 3
systemctl status zheye --no-pager | head -10

echo ""
echo "=== Setup Complete at $(date) ==="
echo "Log saved to: $LOGFILE"
echo "CHANGED_FILES:"
git diff HEAD~1 --name-only 2>/dev/null || echo "Could not determine changed files"
