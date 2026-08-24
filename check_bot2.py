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
    if out: print(f"  OUT: {out[:800]}")
    if err:
        lines = [l for l in err.split('\n') if l.strip()]
        if lines: print(f"  ERR: {'; '.join(lines)[:500]}")
    return out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASS, timeout=15)
print("Connected!\n")

print("=== Bot service status ===")
run(ssh, "systemctl is-active oxycode-bot")

print("\n=== Bot process ===")
run(ssh, "ps aux | grep python | grep -v grep")

print("\n=== Bot logs (last 30 lines) ===")
run(ssh, "journalctl -u oxycode-bot --no-pager -n 30 2>&1")

print("\n=== Bot .env ===")
run(ssh, "grep -v PASSWORD /root/oxycode-bot/.env 2>&1 | grep -v TOKEN | grep -v SECRET")

print("\n=== Bot file exists? ===")
run(ssh, "ls -la /root/oxycode-bot/*.py 2>&1 | head -10")

print("\n=== Bot service file ===")
run(ssh, "cat /etc/systemd/system/oxycode-bot.service 2>&1")

print("\n=== API logs (last 10) ===")
run(ssh, "journalctl -u oxycode-api --no-pager -n 10 2>&1")

ssh.close()
print("\n=== DONE ===")
