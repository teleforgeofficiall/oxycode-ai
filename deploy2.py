import paramiko
VPS_HOST = "153.75.247.105"
VPS_USER = "root"
VPS_PASS = "Snapbucks@Billion"

def run(ssh, cmd, timeout=30):
    print(f"  > {cmd[:120]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    try:
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
    except:
        out = err = "(timeout)"
    if out: print(f"  OUT: {out[:300]}")
    if err:
        lines = [l for l in err.split('\n') if l.strip()]
        if lines: print(f"  ERR: {'; '.join(lines)[:300]}")
    return out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASS, timeout=15)
print("Connected!\n")

print("=== Deploy updated api_server.py ===")
run(ssh, "curl -sL https://files.catbox.moe/4ufwbk.py -o /root/oxycode-bot/api_server.py", timeout=30)

print("\n=== Restart API ===")
run(ssh, "systemctl restart oxycode-api", timeout=30)

import time; time.sleep(3)

print("\n=== Verify ===")
run(ssh, "systemctl is-active oxycode-api")
run(ssh, "curl -s --max-time 5 http://127.0.0.1:8000/api/health")

ssh.close()
print("\n=== DONE ===")
