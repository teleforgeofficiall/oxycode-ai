import paramiko

VPS_HOST = "YOUR_VPS_IP"
VPS_USER = "root"
VPS_PASS = "YOUR_VPS_PASSWORD"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASS, timeout=15)

stdin, stdout, stderr = ssh.exec_command("curl -sI https://oxycode-miniapp.pages.dev 2>&1 | head -5", timeout=15)
out = stdout.read().decode('utf-8', errors='replace')
print(out)

stdin, stdout, stderr = ssh.exec_command("curl -sI https://37e9ac5e.oxycode-miniapp.pages.dev 2>&1 | head -5", timeout=15)
out = stdout.read().decode('utf-8', errors='replace')
print(out)

ssh.close()
