import psycopg2

new_db = 'postgresql://neondb_owner:npg_T3vODNYwA5Rg@ep-green-glitter-afigkd43-pooler.c-2.us-west-2.aws.neon.tech/oxygent_clone?sslmode=require'

conn = psycopg2.connect(new_db)
conn.autocommit = True
cur = conn.cursor()

cur.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    is_banned BOOLEAN DEFAULT FALSE,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    referred_by BIGINT,
    bonus_messages INTEGER DEFAULT 0,
    referrer_id BIGINT
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS channels (
    channel_id BIGINT PRIMARY KEY,
    channel_name TEXT NOT NULL,
    channel_username TEXT,
    added_by BIGINT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

cur.execute('''CREATE TABLE IF NOT EXISTS user_states (
    user_id BIGINT PRIMARY KEY,
    state TEXT,
    data TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS daily_messages (
    user_id BIGINT,
    msg_date DATE,
    count INTEGER DEFAULT 0,
    PRIMARY KEY(user_id, msg_date)
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS admin_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS broadcasts (
    id SERIAL PRIMARY KEY,
    message_text TEXT,
    sent_by BIGINT,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_sent INTEGER DEFAULT 0,
    total_failed INTEGER DEFAULT 0
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS referrals (
    id SERIAL PRIMARY KEY,
    referrer_id BIGINT,
    referred_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

print('All tables created in oxygent_clone!')

cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
tables = cur.fetchall()
print(f'Tables: {[t[0] for t in tables]}')

cur.close()
conn.close()
