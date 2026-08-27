import paramiko
import sys
sys.stdout.reconfigure(encoding='utf-8')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('YOUR_VPS_IP', username='root', password='YOUR_VPS_PASSWORD', timeout=15)

# Check what secrets GitHub found
cmds = [
    ('Check diff for secrets', 'cd /tmp/oxycode-git && git diff HEAD~1 --unified=0 | grep -i -E "(sk-|token|password|secret|key|pat|bearer)" | head -30'),
    ('Check env files', 'cd /tmp/oxycode-git && find . -name ".env" -o -name ".prod.vars" -o -name ".dev.vars" | head -10'),
    ('Check .gitignore', 'cd /tmp/oxycode-git && cat .gitignore'),
]

for label, cmd in cmds:
    print(f'\n> {label}:')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out:
        for line in out.split('\n')[:20]:
            print(f'  {line}')
    if err:
        print(f'  ERR: {err[:200]}')

ssh.close()
