"""Deploy CLONE BOT files to VPS via SSH (paramiko)."""
import paramiko, sys, io, os, time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

IP = '153.75.247.105'
USER = 'root'
PASS = 'Snapbucks@Billion'
LOCAL = r'C:\Users\Teleforge\Desktop\OXYCODE AI BOT\CLONE BOT'
REMOTE = '/root/oxygent-clone'

FILES_TO_UPLOAD = [
    'main.py',
    'database.py',
    'agent_engine.py',
    'config.py',
    'coding_tools.py',
    'memory_system.py',
    'context_engine.py',
    'payments.py',
    'tools.py',
    'requirements.txt',
]

print("=== Deploying to Clone Bot VPS ===")
print(f"Target: {USER}@{IP}:{REMOTE}")
print()

# Connect
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(IP, username=USER, password=PASS, timeout=15)
print("[1/4] SSH connected")

sftp = ssh.open_sftp()

# Upload files
uploaded = 0
for f in FILES_TO_UPLOAD:
    local_path = os.path.join(LOCAL, f)
    remote_path = f"{REMOTE}/{f}"
    if os.path.exists(local_path):
        sftp.put(local_path, remote_path)
        print(f"  Uploaded: {f}")
        uploaded += 1
    else:
        print(f"  SKIPPED (not found): {f}")

sftp.close()
print(f"\n[2/4] {uploaded} files uploaded")

# Clear cache and restart
print("\n[3/4] Clearing cache...")
stdin, stdout, stderr = ssh.exec_command(f"rm -rf {REMOTE}/__pycache__")
stdout.read()

print("[4/4] Restarting clone bot...")
stdin, stdout, stderr = ssh.exec_command("pm2 restart oxygent-clone")
print(stdout.read().decode('utf-8', errors='replace'))

time.sleep(4)

# Check status
stdin, stdout, stderr = ssh.exec_command("pm2 logs oxygent-clone --lines 5 --nostream")
logs = stdout.read().decode('utf-8', errors='replace')
print(f"\n=== Recent Logs ===\n{logs}")

stdin, stdout, stderr = ssh.exec_command("pm2 list | grep oxygent")
status = stdout.read().decode('utf-8', errors='replace')
print(f"=== PM2 Status ===\n{status}")

ssh.close()
print("\n=== Deploy Complete ===")
