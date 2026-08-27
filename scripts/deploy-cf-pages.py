"""Deploy to Cloudflare Pages via VPS."""
import paramiko
import time

VPS_HOST = "YOUR_VPS_IP"
VPS_USER = "root"
VPS_PASS = "YOUR_VPS_PASSWORD"
LOCAL_ZIP = r"C:\Users\Teleforge\Desktop\OXYCODE AI BOT\dist-deploy.zip"
REMOTE_ZIP = "/tmp/oxycode-dist.zip"
REMOTE_EXTRACT = "/tmp/oxycode-dist"

def main():
    print("[1/4] Connecting to VPS...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASS, timeout=15)
    print("  Connected!")

    print("[2/4] Uploading dist zip...")
    sftp = ssh.open_sftp()
    sftp.put(LOCAL_ZIP, REMOTE_ZIP)
    sftp.close()
    print("  Uploaded!")

    print("[3/4] Running DB migration + extracting on VPS...")
    commands = [
        # Extract dist
        f"rm -rf {REMOTE_EXTRACT} && mkdir -p {REMOTE_EXTRACT} && cd {REMOTE_EXTRACT} && unzip -o {REMOTE_ZIP}",
        # DB migration - add agent_type column
        "psql -U postgres -d oxycode -c \"ALTER TABLE chats ADD COLUMN IF NOT EXISTS agent_type TEXT DEFAULT 'oxygent';\" 2>&1 || echo 'DB migration skipped (table may not exist yet)'",
        # Copy to CF Pages functions dir if exists
        f"ls {REMOTE_EXTRACT}/functions/ 2>/dev/null && echo 'Functions found' || echo 'No functions dir'",
    ]
    for cmd in commands:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
        out = stdout.read().decode('utf-8', errors='replace').strip()
        err = stderr.read().decode('utf-8', errors='replace').strip()
        if out:
            print(f"  {out}")
        if err and 'unzip' not in err.lower():
            print(f"  (stderr) {err}")

    print("[4/4] Deploying to Cloudflare Pages...")
    # Deploy using wrangler
    deploy_cmd = f"cd {REMOTE_EXTRACT} && npx wrangler pages deploy . --project-name=oxycode-miniapp --branch=main 2>&1"
    stdin, stdout, stderr = ssh.exec_command(deploy_cmd, timeout=120)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    print(out)
    if err:
        print(f"(stderr) {err}")

    # Cleanup
    ssh.exec_command(f"rm -rf {REMOTE_ZIP} {REMOTE_EXTRACT}")
    ssh.close()
    print("\nDone!")

if __name__ == "__main__":
    main()
