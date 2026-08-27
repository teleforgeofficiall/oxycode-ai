import paramiko
import sys

VPS_HOST = "YOUR_VPS_IP"
VPS_USER = "root"
VPS_PASS = "YOUR_VPS_PASSWORD"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASS, timeout=15)

# DB migration
print("[1] Running DB migration...")
stdin, stdout, stderr = ssh.exec_command(
    "sudo -u postgres psql -d oxycode -c \"ALTER TABLE chats ADD COLUMN IF NOT EXISTS agent_type TEXT DEFAULT 'oxygent';\"",
    timeout=30
)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(out)
if err:
    print(f"stderr: {err}")

# Deploy to CF Pages - write output to file to avoid encoding issues
print("[2] Deploying to CF Pages...")
stdin, stdout, stderr = ssh.exec_command(
    "cd /tmp/oxycode-dist && npx wrangler pages deploy . --project-name=oxycode-miniapp --branch=main > /tmp/cf-deploy.log 2>&1; echo EXIT_CODE=$? >> /tmp/cf-deploy.log",
    timeout=300
)
stdout.read()

# Read the log file
stdin, stdout, stderr = ssh.exec_command("cat /tmp/cf-deploy.log", timeout=30)
log = stdout.read().decode('utf-8', errors='replace')
with open(r"C:\Users\Teleforge\Desktop\OXYCODE AI BOT\scripts\deploy-log.txt", "w", encoding="utf-8") as f:
    f.write(log)
print("Deploy log saved to scripts/deploy-log.txt")

# Cleanup
ssh.exec_command("rm -rf /tmp/oxycode-dist /tmp/oxycode-dist.zip /tmp/cf-deploy.log")
ssh.close()
print("Done!")
