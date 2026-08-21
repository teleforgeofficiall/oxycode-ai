"""
OXYCODE AI — VPS Deployment Script (Robust)
=============================================
Deploys bot + API to VPS with proper SSH session handling.
"""

import paramiko
import time
import sys
import os

VPS_HOST = "153.75.247.105"
VPS_USER = "root"
VPS_PASS = "Snapbucks@Billion"
VPS_PORT = 22
BOT_DIR = "/root/oxycode-bot"
LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))


def connect_vps():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[+] Connecting to {VPS_HOST}...")
    client.connect(VPS_HOST, port=VPS_PORT, username=VPS_USER, password=VPS_PASS, timeout=30)
    print("[+] Connected!")
    return client


def run_cmd(client, cmd, description=None, timeout=300):
    if description:
        print(f"\n--- {description}")
    print(f"    $ {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    exit_status = stdout.channel.recv_exit_status()
    output = stdout.read().decode(errors="replace")
    error = stderr.read().decode(errors="replace")

    if output.strip():
        for line in output.strip().split("\n")[:10]:
            print(f"    {line}")
        if output.count("\n") > 10:
            print(f"    ... ({output.count(chr(10))+1} lines total)")

    if exit_status != 0 and error.strip():
        print(f"    [WARN] exit={exit_status}: {error[:300]}")

    return exit_status, output, error


def upload_file(sftp, local_path, remote_path):
    try:
        sftp.put(local_path, remote_path)
        print(f"    [OK] {os.path.basename(local_path)}")
        return True
    except Exception as e:
        print(f"    [FAIL] {os.path.basename(local_path)}: {e}")
        return False


def deploy():
    client = connect_vps()

    try:
        # Step 1: Create directory
        run_cmd(client, f"mkdir -p {BOT_DIR}", "Creating bot directory...")

        # Step 2: Install dependencies
        run_cmd(client,
            "pip3 install python-telegram-bot aiohttp fastapi uvicorn psycopg2-binary python-dotenv PyJWT pydantic httpx",
            "Installing Python dependencies...",
            timeout=180
        )

        # Step 3: Upload files
        print("\n--- Uploading bot files...")
        sftp = client.open_sftp()

        bot_files = [
            "main.py", "config.py", "database.py", "api_server.py",
            "cloudflare_oauth.py", "cloudflare_deploy.py",
            "project_analyzer.py", "error_fix.py", "requirements.txt",
        ]

        for filename in bot_files:
            local_path = os.path.join(LOCAL_DIR, filename)
            remote_path = f"{BOT_DIR}/{filename}"
            upload_file(sftp, local_path, remote_path)

        # Upload templates
        run_cmd(client, f"mkdir -p {BOT_DIR}/templates")
        tpl = os.path.join(LOCAL_DIR, "templates", "cloudflare_callback.html")
        if os.path.exists(tpl):
            upload_file(sftp, tpl, f"{BOT_DIR}/templates/cloudflare_callback.html")

        sftp.close()

        # Step 4: Create .env with maintenance ON
        env_content = """# OXYCODE AI Environment Variables
BOT_TOKEN=
ADMIN_IDS=8972944701,7371674958
DATABASE_URL=
JWT_SECRET=oxycode-secret-change-this-in-production
MAINTENANCE_MODE=true
CLOUDFLARE_CLIENT_ID=
CLOUDFLARE_CLIENT_SECRET=
CLOUDFLARE_REDIRECT_URI=https://153.75.247.105:8000/cloudflare-callback
"""
        sftp = client.open_sftp()
        with sftp.open(f"{BOT_DIR}/.env", "w") as f:
            f.write(env_content)
        sftp.close()
        print("\n    [OK] .env created (MAINTENANCE_MODE=true)")

        # Step 5: Create systemd services
        bot_service = f"""[Unit]
Description=OXYCODE AI Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory={BOT_DIR}
ExecStart=/usr/bin/python3 {BOT_DIR}/main.py
Restart=always
RestartSec=10
Environment=PYTHONIOENCODING=utf-8

[Install]
WantedBy=multi-user.target
"""

        api_service = f"""[Unit]
Description=OXYCODE AI API Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory={BOT_DIR}
ExecStart=/usr/bin/python3 -m uvicorn api_server:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
Environment=PYTHONIOENCODING=utf-8

[Install]
WantedBy=multi-user.target
"""

        sftp = client.open_sftp()
        with sftp.open("/etc/systemd/system/oxycode-bot.service", "w") as f:
            f.write(bot_service)
        with sftp.open("/etc/systemd/system/oxycode-api.service", "w") as f:
            f.write(api_service)
        sftp.close()
        print("\n    [OK] systemd services created")

        # Step 6: Enable and start services
        run_cmd(client, "systemctl daemon-reload", "Reloading systemd...")
        run_cmd(client, "systemctl enable oxycode-bot oxycode-api", "Enabling services...")
        run_cmd(client, "systemctl restart oxycode-api", "Starting API server...")
        time.sleep(3)
        run_cmd(client, "systemctl restart oxycode-bot", "Starting bot...")

        # Step 7: Check status
        time.sleep(2)
        run_cmd(client, "systemctl is-active oxycode-api", "API status:")
        run_cmd(client, "systemctl is-active oxycode-bot", "Bot status:")

        print("\n" + "=" * 60)
        print("  DEPLOYMENT COMPLETE!")
        print("=" * 60)
        print(f"\n  Bot directory: {BOT_DIR}")
        print(f"  API server:    http://{VPS_HOST}:8000")
        print(f"  Maintenance:   ENABLED (only admins can use)")
        print(f"\n  NEXT STEPS:")
        print(f"  1. SSH: ssh root@{VPS_HOST}")
        print(f"  2. Edit: nano {BOT_DIR}/.env")
        print(f"  3. Fill BOT_TOKEN, DATABASE_URL, JWT_SECRET")
        print(f"  4. Restart: systemctl restart oxycode-bot oxycode-api")

    finally:
        client.close()


if __name__ == "__main__":
    deploy()
