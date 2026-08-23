import paramiko, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

host = "153.75.247.105"
user = "root"
password = "Snapbucks@Billion"
base = r"C:\Users\Teleforge\Desktop\OXYCODE AI BOT\MAIN BOT"
remote_dir = "/root/oxycode-bot"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, 22, user, password, timeout=10)
print("Connected!")

# Upload changed files
sftp = ssh.open_sftp()
for f in ["main.py", "api_server.py", "providers.py", "agent_engine.py"]:
    sftp.put(f"{base}\\{f}", f"{remote_dir}/{f}")
    print(f"Uploaded: {f}")
sftp.close()

# Restart via systemd (safe — only OXYCODE)
stdin, stdout, stderr = ssh.exec_command("systemctl restart oxycode-bot oxycode-api; echo restarted", timeout=10)
print(stdout.read().decode().strip())

time.sleep(12)

# Check journalctl for clean startup
stdin, stdout, stderr = ssh.exec_command("journalctl -u oxycode-bot --no-pager -n 5 2>/dev/null", timeout=8)
print(f"\nJournal:\n{stdout.read().decode().strip()}")

# Verify no conflicts
stdin, stdout, stderr = ssh.exec_command("journalctl -u oxycode-bot --no-pager --since '1 min ago' 2>/dev/null | grep -c Conflict", timeout=8)
conflicts = stdout.read().decode().strip()
print(f"\nConflicts (last min): {conflicts}")

ssh.close()
print("\nDeploy complete!")
