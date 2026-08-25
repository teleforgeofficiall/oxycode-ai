import paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "153.75.247.105", "root", "Snapbucks@Billion"
SCRIPT = sys.argv[1] if len(sys.argv) > 1 else "test_apikey.sh"
LOCAL = rf"C:\Users\Teleforge\Desktop\OXYCODE AI BOT\{SCRIPT}"
TIMEOUT = int(sys.argv[2]) if len(sys.argv) > 2 else 300

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=15)
sftp = c.open_sftp()
sftp.put(LOCAL, f"/tmp/{SCRIPT}")
sftp.close()
stdin, stdout, stderr = c.exec_command(f"bash /tmp/{SCRIPT} 2>&1", timeout=TIMEOUT)
print(stdout.read().decode("utf-8", "replace"))
err = stderr.read().decode("utf-8", "replace")
if err.strip():
    print("[STDERR]", err[:600])
c.close()
