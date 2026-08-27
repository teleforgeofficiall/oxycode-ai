import paramiko

VPS_HOST = "YOUR_VPS_IP"
VPS_USER = "root"
VPS_PASS = "YOUR_VPS_PASSWORD"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASS, timeout=15)

# Check CSRF endpoint directly on VPS API
cmds = [
    ("Direct API", "curl -s http://localhost:8000/api/auth/csrf-token 2>&1"),
    ("DuckDNS", "curl -s https://oxycode.duckdns.org/api/auth/csrf-token 2>&1"),
    ("CF Pages proxy", "curl -s 'https://oxycode-miniapp.pages.dev/api/auth/csrf-token' -H 'Origin: https://oxycode-miniapp.pages.dev' 2>&1"),
]

for label, cmd in cmds:
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    out = stdout.read().decode('utf-8', errors='replace')[:500]
    with open(rf"C:\Users\Teleforge\Desktop\OXYCODE AI BOT\scripts\csrf-{label.lower().replace(' ', '-')}.txt", "w", encoding="utf-8") as f:
        f.write(out)

# Also check the CF Pages function
stdin, stdout, stderr = ssh.exec_command("curl -sI 'https://oxycode-miniapp.pages.dev/api/auth/csrf-token' 2>&1 | head -10", timeout=15)
out = stdout.read().decode('utf-8', errors='replace')
with open(r"C:\Users\Teleforge\Desktop\OXYCODE AI BOT\scripts\csrf-headers.txt", "w", encoding="utf-8") as f:
    f.write(out)

ssh.close()
print("Done")
