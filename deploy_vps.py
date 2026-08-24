import paramiko
import time

VPS_HOST = "153.75.247.105"
VPS_USER = "root"
VPS_PASS = "Snapbucks@Billion"
DUCKDNS_TOKEN = "13207c17-05e1-4908-a9f6-5f61ff8dd141"
DUCKDNS_DOMAIN = "oxycode"

def run(ssh, cmd, timeout=30):
    print(f"  > {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(f"  OUT: {out[:500]}")
    if err:
        # Filter out common non-error stderr
        lines = [l for l in err.split('\n') if l.strip() and 'Warning' not in l and 'deprecated' not in l.lower()]
        if lines:
            print(f"  ERR: {'; '.join(lines)[:500]}")
    return out, err

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {VPS_HOST}...")
    ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASS, timeout=15)
    print("Connected!\n")

    # Step 1: Update DuckDNS IP
    print("=== Step 1: Update DuckDNS IP ===")
    run(ssh, f'curl -s "https://www.duckdns.org/update?domains={DUCKDNS_DOMAIN}&token={DUCKDNS_TOKEN}&ip=153.75.247.105&verbose=true"')
    print()

    # Step 2: Install nginx + certbot
    print("=== Step 2: Install nginx + certbot ===")
    run(ssh, "apt-get update -qq", timeout=60)
    run(ssh, "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nginx certbot python3-certbot-nginx curl > /dev/null 2>&1", timeout=120)
    run(ssh, "systemctl enable nginx && systemctl start nginx")
    print()

    # Step 3: Setup DuckDNS cron
    print("=== Step 3: Setup DuckDNS IP auto-update cron ===")
    cron = f"*/5 * * * * root curl -s 'https://www.duckdns.org/update?domains={DUCKDNS_DOMAIN}&token={DUCKDNS_TOKEN}&ip=$(curl -s https://api.ipify.org)' > /tmp/duck.log 2>&1"
    run(ssh, f"echo '{cron}' > /etc/cron.d/duckdns")
    run(ssh, "chmod 644 /etc/cron.d/duckdns")
    print()

    # Step 4: Configure nginx
    print("=== Step 4: Configure nginx ===")
    nginx_conf = f"""server {{
    listen 80;
    server_name {DUCKDNS_DOMAIN}.duckdns.org;
    
    location / {{
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }}
}}"""
    # Write nginx config using heredoc
    run(ssh, f"cat > /etc/nginx/sites-available/oxycode << 'NGINXEOF'\n{nginx_conf}\nNGINXEOF")
    run(ssh, "ln -sf /etc/nginx/sites-available/oxycode /etc/nginx/sites-enabled/oxycode")
    run(ssh, "rm -f /etc/nginx/sites-enabled/default")
    run(ssh, "nginx -t")
    run(ssh, "systemctl restart nginx")
    print()

    # Step 5: Wait for DNS
    print("=== Step 5: Wait for DNS propagation ===")
    for i in range(1, 19):
        out, _ = run(ssh, f"dig +short {DUCKDNS_DOMAIN}.duckdns.org @1.1.1.1 2>/dev/null | head -1")
        if "153.75.247.105" in out:
            print(f"  DNS propagated! {DUCKDNS_DOMAIN}.duckdns.org -> 153.75.247.105")
            break
        print(f"  Waiting... ({i}/18)")
        time.sleep(5)
    print()

    # Step 6: Get SSL certificate
    print("=== Step 6: Get SSL certificate ===")
    run(ssh, f"certbot --nginx -d {DUCKDNS_DOMAIN}.duckdns.org --non-interactive --agree-tos --email admin@duckdns.org --redirect 2>&1", timeout=120)
    print()

    # Step 7: Deploy updated api_server.py
    print("=== Step 7: Deploy updated api_server.py ===")
    run(ssh, "cp /root/oxycode-bot/api_server.py /root/oxycode-bot/api_server.py.bak 2>/dev/null || true")
    run(ssh, "curl -sL https://files.catbox.moe/1upn83.py -o /root/oxycode-bot/api_server.py", timeout=30)
    print()

    # Step 8: Set WEBSOCKET_BASE_URL env var
    print("=== Step 8: Set WebSocket URL env var ===")
    run(ssh, f"grep -q 'WEBSOCKET_BASE_URL' /root/oxycode-bot/.env && sed -i 's|WEBSOCKET_BASE_URL=.*|WEBSOCKET_BASE_URL=wss://{DUCKDNS_DOMAIN}.duckdns.org|' /root/oxycode-bot/.env || echo 'WEBSOCKET_BASE_URL=wss://{DUCKDNS_DOMAIN}.duckdns.org' >> /root/oxycode-bot/.env")
    print()

    # Step 9: Restart services
    print("=== Step 9: Restart services ===")
    run(ssh, "systemctl restart oxycode-api 2>&1 || true")
    run(ssh, "systemctl restart oxycode-bot 2>&1 || true")
    print()

    # Step 10: Verify
    print("=== Step 10: Verify ===")
    out, _ = run(ssh, "curl -sk https://oxycode.duckdns.org/api/health 2>&1")
    print(f"  Health check: {out[:300]}")
    print()

    # Check SSL
    out, _ = run(ssh, "curl -skI https://oxycode.duckdns.org/ 2>&1 | head -5")
    print(f"  SSL check: {out[:300]}")

    ssh.close()
    print("\n=== DONE ===")

if __name__ == "__main__":
    main()
