"""Check VPS clone bot status."""
import paramiko, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('153.75.247.105', username='root', password='Snapbucks@Billion', timeout=15)

# Syntax check on VPS
cmds = [
    ('agent_engine.py', 'python3 -c "import py_compile; py_compile.compile(\'/root/oxygent-clone/agent_engine.py\', doraise=True); print(\'OK\')"'),
    ('main.py', 'python3 -c "import py_compile; py_compile.compile(\'/root/oxygent-clone/main.py\', doraise=True); print(\'OK\')"'),
    ('database.py', 'python3 -c "import py_compile; py_compile.compile(\'/root/oxygent-clone/database.py\', doraise=True); print(\'OK\')"'),
]

for name, cmd in cmds:
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    print(f'{name}: {out or err}')

# Clear old error logs and restart
ssh.exec_command('pm2 flush oxygent-clone')
ssh.exec_command('pm2 restart oxygent-clone')

import time
time.sleep(5)

# Get fresh logs
stdin, stdout, stderr = ssh.exec_command('pm2 logs oxygent-clone --lines 8 --nostream')
print('\n=== Fresh Logs ===')
print(stdout.read().decode('utf-8', errors='replace'))

ssh.close()
