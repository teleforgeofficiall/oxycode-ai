import paramiko

VPS_HOST = "YOUR_VPS_IP"
VPS_USER = "root"
VPS_PASS = "YOUR_VPS_PASSWORD"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASS, timeout=15)

# Check if functions dir was in the deployed dist
cmds = [
    # Check the function from VPS with proper headers
    "curl -s -H 'Accept: application/json' -H 'Origin: https://oxycode-miniapp.pages.dev' 'https://oxycode-miniapp.pages.dev/api/auth/csrf-token' 2>&1 | head -c 300",
    # Try with cookies
    "curl -s -b 'oxycode_token=fake' 'https://oxycode-miniapp.pages.dev/api/auth/csrf-token' 2>&1 | head -c 300",
    # Check CF Pages function logs
    "curl -sI 'https://oxycode-miniapp.pages.dev/api/' 2>&1 | head -10",
]

for i, cmd in enumerate(cmds):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    out = stdout.read().decode('utf-8', errors='replace')
    with open(rf"C:\Users\Teleforge\Desktop\OXYCODE AI BOT\scripts\proxy-test-{i}.txt", "w", encoding="utf-8") as f:
        f.write(out)

ssh.close()
print("Done")
