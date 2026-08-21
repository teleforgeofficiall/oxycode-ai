import psycopg2

new_db = 'postgresql://neondb_owner:npg_T3vODNYwA5Rg@ep-green-glitter-afigkd43-pooler.c-2.us-west-2.aws.neon.tech/oxygent_clone?sslmode=require'

conn = psycopg2.connect(new_db)
conn.autocommit = True
cur = conn.cursor()

# Drop wrong tables
cur.execute("DROP TABLE IF EXISTS admin_settings CASCADE")
cur.execute("DROP TABLE IF EXISTS referrals CASCADE")
cur.execute("DROP TABLE IF EXISTS daily_messages CASCADE")

# Create ALL tables matching main bot schema exactly
cur.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    github_repo TEXT,
    github_token TEXT,
    is_setup INTEGER DEFAULT 0,
    is_banned INTEGER DEFAULT 0,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    referral_code TEXT,
    referred_by BIGINT DEFAULT 0,
    bonus_messages INTEGER DEFAULT 0,
    msg_count INTEGER DEFAULT 0,
    msg_date TEXT,
    ref_credited INTEGER DEFAULT 0,
    voice_enabled INTEGER DEFAULT 0,
    voice_gender TEXT DEFAULT 'female'
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS channels (
    channel_id BIGINT PRIMARY KEY,
    channel_name TEXT NOT NULL,
    channel_username TEXT,
    added_by BIGINT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS broadcasts (
    id SERIAL PRIMARY KEY,
    message_text TEXT,
    sent_by INTEGER,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_users INTEGER,
    successful INTEGER
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS user_states (
    user_id BIGINT PRIMARY KEY,
    state TEXT,
    data TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS workers (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE,
    worker_name TEXT NOT NULL,
    worker_type TEXT DEFAULT 'website',
    worker_url TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    telegram_charge_id TEXT UNIQUE,
    invoice_payload TEXT,
    stars INTEGER,
    credits_added INTEGER,
    currency TEXT DEFAULT 'XTR',
    status TEXT DEFAULT 'completed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS code_sessions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    session_name TEXT NOT NULL,
    project_type TEXT,
    context_data TEXT,
    code_files TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, session_name)
)''')

# Insert default settings
cur.execute("INSERT INTO settings (key, value) VALUES ('daily_limit', '20') ON CONFLICT (key) DO NOTHING")
cur.execute("INSERT INTO settings (key, value) VALUES ('referral_bonus', '20') ON CONFLICT (key) DO NOTHING")
cur.execute("INSERT INTO settings (key, value) VALUES ('max_sessions', '5') ON CONFLICT (key) DO NOTHING")

print("All tables created with correct schema!")

cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
tables = cur.fetchall()
print(f"Tables: {[t[0] for t in tables]}")

cur.close()
conn.close()
