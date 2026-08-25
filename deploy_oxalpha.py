import paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "153.75.247.105", "root", "Snapbucks@Billion"
STAMP = "20260826_quota_final"
FILES = [
    (r"C:\Users\Teleforge\Desktop\OXYCODE AI BOT\vps_sync\database.py", "/root/oxycode-bot/database.py"),
    (r"C:\Users\Teleforge\Desktop\OXYCODE AI BOT\vps_sync\api_server.py", "/root/oxycode-bot/api_server.py"),
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=15)

def run(cmd, timeout=60):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    return out, err

# 1. Backup
backup_cmds = " && ".join([f"cp {r} {r}.bak.{STAMP}" for _, r in FILES])
o, e = run(f"{backup_cmds} && ls /root/oxycode-bot/*.bak.{STAMP}")
print("[BACKUP]\n" + o + e)

# 2. Upload
sftp = c.open_sftp()
for local, remote in FILES:
    sftp.put(local, remote)
    print(f"[UPLOADED] {remote}")
sftp.close()

# 3. Syntax check
compile_files = " ".join([r.split("/")[-1] for _, r in FILES])
o, e = run(f"cd /root/oxycode-bot && python3 -m py_compile {compile_files} && echo COMPILE_OK")
print("[COMPILE]\n" + o + e)
if "COMPILE_OK" not in o:
    print("!! Compile failed - restoring backups !!")
    restore_cmds = " && ".join([f"cp {r}.bak.{STAMP} {r}" for _, r in FILES])
    run(f"{restore_cmds} && systemctl restart oxycode-api")
    sys.exit(1)

# 4. Restart
o, e = run("systemctl restart oxycode-api && sleep 3 && systemctl is-active oxycode-api")
print("[RESTART]\n" + o + e)

# 5. Logs
o, e = run("journalctl -u oxycode-api --no-pager -n 12 --output=cat")
print("[LOGS]\n" + o + e)

c.close()
print("DEPLOY_DONE")
