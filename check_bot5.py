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
    if out: print(f"  OUT: {out[:1000]}")
    if err:
        lines = [l for l in err.split('\n') if l.strip()]
        if lines: print(f"  ERR: {'; '.join(lines)[:500]}")
    return out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASS, timeout=15)
print("Connected!\n")

print("=== Bot running? ===")
run(ssh, "systemctl is-active oxycode-bot")

print("\n=== Recent bot logs ===")
run(ssh, "journalctl -u oxycode-bot --no-pager -n 20 2>&1")

print("\n=== Any errors after restart? ===")
run(ssh, "journalctl -u oxycode-bot --no-pager --since '2026-08-24 04:19:00' 2>&1 | grep -i 'error\\|ERROR' | head -10")

print("\n=== Network: can reach Telegram? ===")
run(ssh, "curl -s --max-time 5 'https://api.telegram.org/bot8677499121:AAFCfGa55PEqpi-MVRtVL1W7HgPc8ikZgWs/getUpdates?offset=-1&limit=1' 2>&1 | python3 -m json.tool 2>&1 | head -20")

ssh.close()
print("\n=== DONE ===")
