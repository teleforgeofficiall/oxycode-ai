import paramiko

VPS_HOST = "YOUR_VPS_IP"
VPS_USER = "root"
VPS_PASS = "YOUR_VPS_PASSWORD"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASS, timeout=15)

cmds = [
    ("csrf-direct", "curl -s http://localhost:8000/api/auth/csrf-token 2>&1"),
    ("csrf-proxy", "curl -s 'https://oxycode-miniapp.pages.dev/api/auth/csrf-token' -H 'Accept: application/json' 2>&1 | head -c 300"),
]

for label, cmd in cmds:
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    out = stdout.read().decode('utf-8', errors='replace')
    path = rf"C:\Users\Teleforge\Desktop\OXYCODE AI BOT\scripts\{label}.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"[{label}] saved")

ssh.close()
