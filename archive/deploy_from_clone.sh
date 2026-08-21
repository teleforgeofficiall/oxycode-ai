#!/bin/bash
# Deploy from Clone Bot to Main Bot
# Copies code files only - database is NOT affected

CLONE_DIR="/root/oxygent-clone"
MAIN_DIR="/root/oxygent-bot"
BACKUP_DIR="/root/oxygent-bot/backups/$(date +%Y%m%d_%H%M%S)"

echo "=== Deploying from Clone to Main ==="
echo ""

# Create backup of main bot code
echo "[1/4] Creating backup..."
mkdir -p "$BACKUP_DIR"
for f in main.py database.py coding_tools.py payments.py agent_engine.py context_engine.py memory_system.py tools.py; do
    if [ -f "$MAIN_DIR/$f" ]; then
        cp "$MAIN_DIR/$f" "$BACKUP_DIR/$f"
        echo "  Backed up: $f"
    fi
done
echo "  Backup saved to: $BACKUP_DIR"
echo ""

# Copy code files from clone to main
echo "[2/4] Copying code files..."
COPIED=0
for f in main.py database.py coding_tools.py payments.py agent_engine.py context_engine.py memory_system.py tools.py; do
    if [ -f "$CLONE_DIR/$f" ]; then
        cp "$CLONE_DIR/$f" "$MAIN_DIR/$f"
        echo "  Copied: $f"
        COPIED=$((COPIED + 1))
    fi
done
echo "  Files copied: $COPIED"
echo ""

# Check if requirements changed
echo "[3/4] Checking requirements..."
if diff -q "$CLONE_DIR/requirements.txt" "$MAIN_DIR/requirements.txt" > /dev/null 2>&1; then
    echo "  Requirements unchanged"
else
    cp "$CLONE_DIR/requirements.txt" "$MAIN_DIR/requirements.txt"
    echo "  Requirements updated - installing..."
    cd "$MAIN_DIR" && source venv/bin/activate && pip install -r requirements.txt -q
fi
echo ""

# Restart main bot
echo "[4/4] Restarting Main Bot..."
pm2 restart oxygent-bot
sleep 3

# Check status
echo ""
echo "=== Deploy Complete ==="
echo ""
pm2 list | grep oxygent
echo ""
echo "Main Bot restarted with Clone Bot code!"
echo "Database: UNCHANGED (same Neon DB)"
echo "Users/Channels/Settings: SAFE"
