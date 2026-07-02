#!/bin/bash
# Background script: sleep 1 hour, then git pull and report changes

LOGFILE="/tmp/zheye-pull-report-$(date +%s).txt"

echo "=== Zheye Git Pull Report ===" > "$LOGFILE"
echo "Started at: $(date)" >> "$LOGFILE"
echo "" >> "$LOGFILE"

# Sleep for 1 hour
echo "Sleeping for 3600 seconds (1 hour)..." >> "$LOGFILE"
sleep 3600

echo "Woke up at: $(date)" >> "$LOGFILE"
echo "" >> "$LOGFILE"

# Pull changes
echo "--- git pull output ---" >> "$LOGFILE"
cd /opt/zheye
git pull 2>&1 >> "$LOGFILE"
PULL_STATUS=$?
echo "" >> "$LOGFILE"

# Check changed files
echo "--- Files changed (last commit diff) ---" >> "$LOGFILE"
CHANGED=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || echo "No previous commit to diff")
echo "$CHANGED" >> "$LOGFILE"
echo "" >> "$LOGFILE"

# Check for dependency changes
echo "--- Dependency changes ---" >> "$LOGFILE"
if echo "$CHANGED" | grep -q "package.json\|requirements.txt\|Gemfile\|go.mod\|Cargo.toml\|pom.xml"; then
    echo "WARNING: Dependency file(s) changed!" >> "$LOGFILE"
    echo "$CHANGED" | grep -E "package.json|requirements.txt|Gemfile|go.mod|Cargo.toml|pom.xml" >> "$LOGFILE"
else
    echo "No dependency file changes detected." >> "$LOGFILE"
fi
echo "" >> "$LOGFILE"

# Check for config changes
echo "--- Config changes ---" >> "$LOGFILE"
if echo "$CHANGED" | grep -qiE "\.env|config|settings|\.yml|\.yaml|\.toml"; then
    echo "Config file(s) changed:" >> "$LOGFILE"
    echo "$CHANGED" | grep -iE "\.env|config|settings|\.yml|\.yaml|\.toml" >> "$LOGFILE"
else
    echo "No config file changes detected." >> "$LOGFILE"
fi
echo "" >> "$LOGFILE"

# Environment requirements check
echo "--- New requirements ---" >> "$LOGFILE"
if echo "$CHANGED" | grep -q "package.json"; then
    echo "New npm packages may need: npm install" >> "$LOGFILE"
fi
if echo "$CHANGED" | grep -q "requirements.txt"; then
    echo "New Python packages may need: pip install -r requirements.txt" >> "$LOGFILE"
fi
if echo "$CHANGED" | grep -q "Dockerfile\|docker-compose"; then
    echo "Docker config changed - may need: docker-compose up --build" >> "$LOGFILE"
fi
if echo "$CHANGED" | grep -q "\.env"; then
    echo "Environment variables changed - check .env file" >> "$LOGFILE"
fi

echo "" >> "$LOGFILE"
echo "=== Report complete ===" >> "$LOGFILE"
echo "Full report saved to: $LOGFILE"
