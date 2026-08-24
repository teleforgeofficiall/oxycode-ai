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

# Check if another bot process is running with same token
print("=== All python processes ===")
run(ssh, "ps aux | grep python | grep -v grep | grep -v unattended")

print("\n=== Bot logs ALL (last 50) ===")
run(ssh, "journalctl -u oxycode-bot --no-pager -n 50 2>&1 | tail -50")

print("\n=== Check if webhook set ===")
run(ssh, "curl -s 'https://api.telegram.org/bot8677499121:AAFCfGa55PEqpi-MVRtVL1W7HgPc8ikZgWs/getWebhookInfo' 2>&1")

print("\n=== Check for errors in bot startup ===")
run(ssh, "journalctl -u oxycode-bot --no-pager -n 100 2>&1 | grep -i 'error\\|Error\\|ERROR\\|traceback\\|exception' | head -20")

print("\n=== Bot PID ===")
run(ssh, "systemctl show oxycode-bot --property=MainPID --value")

print("\n=== Check if taskhub bot uses same token ===")
run(ssh, "grep -r 'BOT_TOKEN\\|telegram.*token' /opt/taskhub/.env 2>/dev/null | head -5")

ssh.close()
print("\n=== DONE ===")
