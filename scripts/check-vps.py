import paramiko
import sys
sys.stdout.reconfigure(encoding='utf-8')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('YOUR_VPS_IP', username='root', password='YOUR_VPS_PASSWORD', timeout=15)

print('=== VPS /root/oxycode-bot contents ===')
stdin, stdout, stderr = ssh.exec_command('ls -la /root/oxycode-bot/')
print(stdout.read().decode())

print('\n=== .prod.vars OPENCODE_API_KEY check ===')
stdin, stdout, stderr = ssh.exec_command('grep OPENCODE_API_KEY /root/oxycode-bot/.prod.vars 2>/dev/null || echo NOT_FOUND')
print(stdout.read().decode())

print('\n=== Git status ===')
stdin, stdout, stderr = ssh.exec_command('cd /root/oxycode-bot && git status --short 2>&1 | head -20')
print(stdout.read().decode())

print('\n=== Git remote ===')
stdin, stdout, stderr = ssh.exec_command('cd /root/oxycode-bot && git remote -v 2>&1')
print(stdout.read().decode())

ssh.close()
