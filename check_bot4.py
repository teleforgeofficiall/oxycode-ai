import paramiko
VPS_HOST = "153.75.247.105"
VPS_USER = "root"
VPS_PASS = "Snapbucks@Billion"

def run(ssh, cmd, timeout=15):
    print(f"  > {cmd[:150]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    try:
        out = stdout.read().decode('utf-8', errors='replace').strip()
        err = stderr.read().decode('utf-8', errors='replace').strip()
    except:
        out = err = "(timeout)"
    if out: print(f"  OUT: {out[:2000]}")
    if err:
        lines = [l for l in err.split('\n') if l.strip()]
        if lines: print(f"  ERR: {'; '.join(lines)[:500]}")
    return out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASS, timeout=15)
print("Connected!\n")

# Get full error traceback
print("=== Full error context ===")
run(ssh, "journalctl -u oxycode-bot --no-pager --since '2026-08-24 04:15:50' --until '2026-08-24 04:16:10' 2>&1")

# Check network connectivity
print("\n=== Network test ===")
run(ssh, "curl -s --max-time 5 -o /dev/null -w '%{http_code}' https://api.telegram.org 2>&1")

# Check DNS
print("\n=== DNS test ===")
run(ssh, "nslookup api.telegram.org 2>&1 | head -5")

# Test direct from VPS
print("\n=== Direct bot API test ===")
run(ssh, "curl -s --max-time 10 'https://api.telegram.org/bot8677499121:AAFCfGa55PEqpi-MVRtVL1W7HgPc8ikZgWs/getMe' 2>&1 | head -3")

# Restart bot cleanly
print("\n=== Restarting bot ===")
run(ssh, "systemctl restart oxycode-bot", timeout=15)

import time
time.sleep(5)

print("\n=== Bot status after restart ===")
run(ssh, "systemctl is-active oxycode-bot")

print("\n=== Bot logs after restart ===")
run(ssh, "journalctl -u oxycode-bot --no-pager -n 15 2>&1")

ssh.close()
print("\n=== DONE ===")
