import paramiko

VPS_HOST = "YOUR_VPS_IP"
VPS_USER = "root"
VPS_PASS = "YOUR_VPS_PASSWORD"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASS, timeout=15)

# Check what databases exist
stdin, stdout, stderr = ssh.exec_command("sudo -u postgres psql -l 2>&1", timeout=15)
out = stdout.read().decode('utf-8', errors='replace')
with open(r"C:\Users\Teleforge\Desktop\OXYCODE AI BOT\scripts\db-check.txt", "w", encoding="utf-8") as f:
    f.write(out)
print("DB list saved to scripts/db-check.txt")

# Also check if oxycode-bot has its own DB
stdin, stdout, stderr = ssh.exec_command("cat /opt/oxycode-bot/.env 2>/dev/null || cat /root/oxycode-bot/.env 2>/dev/null || echo 'No .env found'", timeout=15)
out = stdout.read().decode('utf-8', errors='replace')
with open(r"C:\Users\Teleforge\Desktop\OXYCODE AI BOT\scripts\env-check.txt", "w", encoding="utf-8") as f:
    f.write(out)
print("Env check saved to scripts/env-check.txt")

ssh.close()
