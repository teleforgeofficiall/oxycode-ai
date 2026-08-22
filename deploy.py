import paramiko, os, time

host = "153.75.247.105"
user = "root"
password = "Snapbucks@Billion"
base = r"C:\Users\Teleforge\Desktop\OXYCODE AI BOT\MAIN BOT"
remote_dir = "/root/oxycode-bot"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, 22, user, password, timeout=10)
print("Connected!")

# Upload files
sftp = ssh.open_sftp()
files = ["main.py", "providers.py", "agent_engine.py", "database.py"]
for f in files:
    local = os.path.join(base, f)
    remote = f"{remote_dir}/{f}"
    sftp.put(local, remote)
    print(f"Uploaded: {f}")
sftp.close()

# Kill old bot
stdin, stdout, stderr = ssh.exec_command("pkill -f 'python3 main.py' || true")
print("Kill:", stdout.read().decode().strip())
time.sleep(2)

# Start bot
stdin, stdout, stderr = ssh.exec_command(f"cd {remote_dir} && nohup python3 main.py > bot.log 2>&1 &")
print("Start:", stdout.read().decode().strip())
time.sleep(4)

# Check log
stdin, stdout, stderr = ssh.exec_command(f"tail -15 {remote_dir}/bot.log")
log = stdout.read().decode().strip()
print("=== Bot Log ===")
print(log)

ssh.close()
print("\nDeploy complete!")
