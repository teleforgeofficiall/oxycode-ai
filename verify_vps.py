import paramiko

VPS_HOST = "153.75.247.105"
VPS_USER = "root"
VPS_PASS = "Snapbucks@Billion"

def run(ssh, cmd, timeout=30):
    print(f"  > {cmd[:120]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(f"  OUT: {out[:800]}")
    if err:
        lines = [l for l in err.split('\n') if l.strip()]
        if lines:
            print(f"  ERR: {'; '.join(lines)[:500]}")
    return out, err

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASS, timeout=15)
    print("Connected!\n")

    # Check .env has WEBSOCKET_BASE_URL
    print("=== Check .env ===")
    out, _ = run(ssh, "grep WEBSOCKET_BASE_URL /root/oxycode-bot/.env")
    print()

    # Check nginx SSL config
    print("=== Check nginx SSL ===")
    out, _ = run(ssh, "cat /etc/nginx/sites-enabled/oxycode")
    print()

    # Check /api/health via HTTPS
    print("=== HTTPS health check ===")
    out, _ = run(ssh, "curl -s https://oxycode.duckdns.org/api/health")
    print()

    # Check /api/user/me (should return 401)
    print("=== HTTPS auth check (should 401) ===")
    out, _ = run(ssh, "curl -s -o /dev/null -w '%{http_code}' https://oxycode.duckdns.org/api/user/me")
    print()

    # Check WebSocket endpoint (should 426 Upgrade Required)
    print("=== WebSocket endpoint check ===")
    out, _ = run(ssh, "curl -s -o /dev/null -w '%{http_code}' -H 'Upgrade: websocket' -H 'Connection: Upgrade' https://oxycode.duckdns.org/ws/1")
    print()

    # Check DuckDNS cron
    print("=== DuckDNS cron ===")
    out, _ = run(ssh, "cat /etc/cron.d/duckdns")
    print()

    # SSL cert expiry
    print("=== SSL cert expiry ===")
    out, _ = run(ssh, "echo | openssl s_client -connect oxycode.duckdns.org:443 2>/dev/null | openssl x509 -noout -dates 2>/dev/null")
    print()

    ssh.close()
    print("=== ALL CHECKS DONE ===")

if __name__ == "__main__":
    main()
