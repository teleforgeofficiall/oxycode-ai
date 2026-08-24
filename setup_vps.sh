#!/bin/bash
# OXYCODE VPS Setup - DuckDNS + nginx + SSL
# Run this on VPS via aaPanel terminal or SSH
#
# PREREQUISITES:
# 1. Register a free subdomain at https://www.duckdns.org
#    - Login with GitHub/Google
#    - Create domain like "oxycode" → you get "oxycode.duckdns.org"
#    - Note your DuckDNS token (shown on the page after creating domain)
#
# USAGE:
#   export DUCKDNS_TOKEN="your-token-here"
#   export DUCKDNS_DOMAIN="oxycode"
#   bash setup_vps.sh

set -e

echo "=== OXYCODE VPS Setup ==="
echo ""

# Check vars
if [ -z "$DUCKDNS_TOKEN" ] || [ -z "$DUCKDNS_DOMAIN" ]; then
    echo "ERROR: Set DUCKDNS_TOKEN and DUCKDNS_DOMAIN first!"
    echo "  export DUCKDNS_TOKEN='your-token'"
    echo "  export DUCKDNS_DOMAIN='oxycode'"
    exit 1
fi

FULL_DOMAIN="${DUCKDNS_DOMAIN}.duckdns.org"
echo "Setting up: $FULL_DOMAIN"
echo ""

# 1. Update system
echo "[1/7] Updating system..."
apt-get update -qq
apt-get install -y -qq curl nginx certbot python3-certbot-nginx cron > /dev/null 2>&1

# 2. Update DuckDNS IP
echo "[2/7] Updating DuckDNS IP..."
PUBLIC_IP=$(curl -s https://api.ipify.org)
curl -s "https://www.duckdns.org/update?domains=${DUCKDNS_DOMAIN}&token=${DUCKDNS_TOKEN}&ip=${PUBLIC_IP}&verbose=true"
echo ""

# 3. Create DuckDNS cron job (auto-update IP every 5 minutes)
echo "[3/7] Setting up DuckDNS IP auto-update cron..."
cat > /etc/cron.d/duckdns << EOF
*/5 * * * * root curl -s "https://www.duckdns.org/update?domains=${DUCKDNS_DOMAIN}&token=${DUCKDNS_TOKEN}&ip=\$(curl -s https://api.ipify.org)" > /tmp/duck.log 2>&1
EOF
chmod 644 /etc/cron.d/duckdns

# 4. Configure nginx
echo "[4/7] Configuring nginx..."
cat > /etc/nginx/sites-available/oxycode << EOF
server {
    listen 80;
    server_name ${FULL_DOMAIN};
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
    }
}
EOF

ln -sf /etc/nginx/sites-available/oxycode /etc/nginx/sites-enabled/oxycode
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

# 5. Wait for DNS propagation
echo "[5/7] Waiting for DNS propagation..."
for i in $(seq 1 12); do
    RESOLVED=$(dig +short $FULL_DOMAIN @1.1.1.1 2>/dev/null | head -1)
    if [ "$RESOLVED" = "$PUBLIC_IP" ]; then
        echo "  DNS propagated! ($FULL_DOMAIN → $PUBLIC_IP)"
        break
    fi
    echo "  Waiting... ($i/12)"
    sleep 5
done

# 6. Get SSL certificate
echo "[6/7] Getting SSL certificate via Let's Encrypt..."
certbot --nginx -d $FULL_DOMAIN --non-interactive --agree-tos --email admin@${FULL_DOMAIN} --redirect 2>&1 || {
    echo "  WARNING: certbot failed. Trying manual DNS challenge..."
    echo "  If this fails, run certbot manually:"
    echo "  certbot certonly --manual --preferred-challenges dns -d $FULL_DOMAIN"
}

# 7. Verify
echo "[7/7] Verifying setup..."
echo ""
echo "=== Setup Complete ==="
echo "  HTTP:  http://$FULL_DOMAIN"
echo "  HTTPS: https://$FULL_DOMAIN"
echo "  API:   https://$FULL_DOMAIN/api/health"
echo "  WS:    wss://$FULL_DOMAIN/ws/{chat_id}"
echo ""
echo "Test: curl https://$FULL_DOMAIN/api/health"
echo ""
echo "Now update api_server.py with:"
echo "  WEBSOCKET_BASE_URL=wss://$FULL_DOMAIN"
echo ""
