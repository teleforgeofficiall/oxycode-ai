import paramiko
import time

VPS_HOST = "153.75.247.105"
VPS_USER = "root"
VPS_PASS = "Snapbucks@Billion"

def run(ssh, cmd, timeout=60):
    print(f"  > {cmd[:120]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(f"  OUT: {out[:500]}")
    if err:
        lines = [l for l in err.split('\n') if l.strip() and 'Warning' not in l]
        if lines:
            print(f"  ERR: {'; '.join(lines)[:500]}")
    return out, err

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {VPS_HOST}...")
    ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASS, timeout=15)
    print("Connected!\n")

    # Step 1: Fix certbot (retry with longer timeout)
    print("=== Step 1: Get SSL certificate (retry) ===")
    out, err = run(ssh, "certbot --nginx -d oxycode.duckdns.org --non-interactive --agree-tos --email admin@duckdns.org --redirect --http-01-port 80", timeout=180)
    print()

    # Step 2: Fix cron job (single quotes broken in previous deploy)
    print("=== Step 2: Fix DuckDNS cron job ===")
    run(ssh, """cat > /etc/cron.d/duckdns << 'EOF'
*/5 * * * * root curl -s "https://www.duckdns.org/update?domains=oxycode&token=13207c17-05e1-4908-a9f6-5f61ff8dd141&ip=$(curl -s https://api.ipify.org)" > /tmp/duck.log 2>&1
EOF
chmod 644 /etc/cron.d/duckdns""")
    print()

    # Step 3: Restart API service
    print("=== Step 3: Restart API service ===")
    run(ssh, "systemctl restart oxycode-api", timeout=30)
    time.sleep(2)
    out, _ = run(ssh, "systemctl is-active oxycode-api")
    print(f"  API status: {out}")
    print()

    # Step 4: Restart bot service
    print("=== Step 4: Restart bot service ===")
    run(ssh, "systemctl restart oxycode-bot", timeout=30)
    time.sleep(2)
    out, _ = run(ssh, "systemctl is-active oxycode-bot")
    print(f"  Bot status: {out}")
    print()

    # Step 5: Verify SSL + API
    print("=== Step 5: Verify ===")
    out, _ = run(ssh, "curl -sk https://oxycode.duckdns.org/api/health 2>&1")
    print(f"  Health: {out[:300]}")
    out, _ = run(ssh, "curl -skI https://oxycode.duckdns.org/ 2>&1 | head -3")
    print(f"  SSL: {out[:300]}")

    # Step 6: Check logs
    print("\n=== Step 6: Check API logs ===")
    out, _ = run(ssh, "journalctl -u oxycode-api --no-pager -n 15 2>&1")
    print(f"  {out[:600]}")

    ssh.close()
    print("\n=== DONE ===")

if __name__ == "__main__":
    main()
