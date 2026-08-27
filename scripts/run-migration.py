import paramiko

VPS_HOST = "YOUR_VPS_IP"
VPS_USER = "root"
VPS_PASS = "YOUR_VPS_PASSWORD"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASS, timeout=15)

# Write a Python migration script on VPS
migration_script = '''
import sys
try:
    import psycopg2
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary", "-q"])
    import psycopg2

DB_URL = "postgresql://neondb_owner:YOUR_NEON_PASSWORD@ep-green-glitter-afigkd43-pooler.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require"

try:
    conn = psycopg2.connect(DB_URL, connect_timeout=15)
    cur = conn.cursor()
    
    # Add agent_type column
    cur.execute("ALTER TABLE chats ADD COLUMN IF NOT EXISTS agent_type TEXT DEFAULT 'oxygent';")
    conn.commit()
    print("SUCCESS: agent_type column added/verified")
    
    # Verify
    cur.execute("SELECT column_name, data_type, column_default FROM information_schema.columns WHERE table_name=%s AND column_name=%s;", ('chats', 'agent_type'))
    row = cur.fetchone()
    if row:
        print(f"Verified: {row}")
    else:
        print("WARNING: column not found after migration")
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
'''

# Upload and run
sftp = ssh.open_sftp()
with sftp.open("/tmp/migrate_agent_type.py", "w") as f:
    f.write(migration_script)
sftp.close()

print("[1] Running migration on Neon...")
stdin, stdout, stderr = ssh.exec_command(
    "cd /tmp && python3 migrate_agent_type.py 2>&1",
    timeout=60
)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
with open(r"C:\Users\Teleforge\Desktop\OXYCODE AI BOT\scripts\migration-result.txt", "w", encoding="utf-8") as f:
    f.write(f"STDOUT:\n{out}\nSTDERR:\n{err}")
print(out)
if err:
    print(f"stderr: {err[:500]}")

ssh.exec_command("rm /tmp/migrate_agent_type.py")
ssh.close()
