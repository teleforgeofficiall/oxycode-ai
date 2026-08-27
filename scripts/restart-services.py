import paramiko

VPS_HOST = "YOUR_VPS_IP"
VPS_USER = "root"
VPS_PASS = "YOUR_VPS_PASSWORD"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASS, timeout=15)

stdin, stdout, stderr = ssh.exec_command(
    "systemctl restart oxycode-bot.service oxycode-api.service 2>&1; sleep 2; systemctl status oxycode-bot.service --no-pager 2>&1 | head -10; echo '---'; systemctl status oxycode-api.service --no-pager 2>&1 | head -10",
    timeout=30
)
out = stdout.read().decode('utf-8', errors='replace')
with open(r"C:\Users\Teleforge\Desktop\OXYCODE AI BOT\scripts\restart-result.txt", "w", encoding="utf-8") as f:
    f.write(out)
print("Result saved to scripts/restart-result.txt")

ssh.close()
