"""One-time migration: add all missing columns to users table + deployments table + settings."""
import os
import psycopg2

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_T3vODNYwA5Rg@ep-green-glitter-afigkd43-pooler.c-2.us-west-2.aws.neon.tech/oxygent_clone?sslmode=require"
)

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Check current columns
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='users'")
cols = [r[0] for r in cur.fetchall()]
print("CURRENT USER COLS:", cols)

# All columns the code expects (from CREATE TABLE + _new_cols migration)
all_expected = {
    "user_id": "BIGINT PRIMARY KEY",
    "username": "TEXT",
    "first_name": "TEXT",
    "last_name": "TEXT",
    "github_repo": "TEXT",
    "github_token": "TEXT",
    "is_setup": "INTEGER DEFAULT 0",
    "is_banned": "INTEGER DEFAULT 0",
    "deploy_count": "INTEGER DEFAULT 0",
    "worker_count": "INTEGER DEFAULT 0",
    "max_deploys": "INTEGER DEFAULT 5",
    "max_workers": "INTEGER DEFAULT 5",
    "joined_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "referred_by": "BIGINT DEFAULT 0",
    "bonus_messages": "INTEGER DEFAULT 0",
    "referrer_id": "BIGINT",
    "msg_count": "INTEGER DEFAULT 0",
    "msg_date": "TEXT",
    "ref_credited": "INTEGER DEFAULT 0",
    "voice_enabled": "INTEGER DEFAULT 0",
    "voice_gender": "TEXT DEFAULT 'female'",
    "referral_code": "TEXT",
}

# Add missing columns
added = []
for col_name, col_type in all_expected.items():
    if col_name not in cols:
        try:
            cur.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            conn.commit()
            added.append(col_name)
            print(f"  Added: {col_name}")
        except Exception as e:
            conn.rollback()
            print(f"  Failed to add {col_name}: {e}")
    else:
        print(f"  Exists: {col_name}")

# Create deployments table
cur.execute("""
    CREATE TABLE IF NOT EXISTS deployments (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        deploy_type TEXT NOT NULL,
        name TEXT NOT NULL,
        url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()
print("Deployments table: OK")

# Add default settings
for key, val in [("global_max_sites", "5"), ("global_max_workers", "5"), ("daily_limit", "20"), ("referral_bonus", "20")]:
    cur.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING", (key, val))
conn.commit()
print("Settings: OK")

# Final verification
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='users'")
final_cols = [r[0] for r in cur.fetchall()]
print("\nFINAL USER COLS:", final_cols)

# Check what's still missing
still_missing = [c for c in all_expected if c not in final_cols]
if still_missing:
    print("\nSTILL MISSING:", still_missing)
else:
    print("\nALL COLUMNS PRESENT!")

conn.close()
print("DONE")
