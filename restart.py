import paramiko, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("153.75.247.105", 22, "root", "Snapbucks@Billion", timeout=10)

# Check API server
stdin, stdout, stderr = ssh.exec_command("curl -s http://127.0.0.1:8000/api/health", timeout=5)
print("Health:", stdout.read().decode().strip())

stdin, stdout, stderr = ssh.exec_command("curl -s http://127.0.0.1:8000/api/status", timeout=5)
print("Status:", stdout.read().decode().strip())

# Check services
stdin, stdout, stderr = ssh.exec_command("systemctl is-active oxycode-bot oxycode-api", timeout=5)
print("Services:", stdout.read().decode().strip())

# Check for conflicts after 1 min
time.sleep(60)
stdin, stdout, stderr = ssh.exec_command("journalctl -u oxycode-bot --no-pager --since '1 min ago' 2>/dev/null | grep -c Conflict", timeout=8)
conflicts = stdout.read().decode().strip()
print(f"\nConflicts (1 min later): {conflicts}")

stdin, stdout, stderr = ssh.exec_command("journalctl -u oxycode-bot --no-pager --since '1 min ago' 2>/dev/null | tail -3", timeout=8)
print(f"Latest:\n{stdout.read().decode().strip()}")

ssh.close()
