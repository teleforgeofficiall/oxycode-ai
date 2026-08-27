import paramiko
import sys
sys.stdout.reconfigure(encoding='utf-8')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('YOUR_VPS_IP', username='root', password='YOUR_VPS_PASSWORD', timeout=15)

PAT = 'YOUR_GITHUB_PAT'

commands = [
    'cd /root/oxycode-bot && git config user.email "admin@oxycode.ai"',
    'cd /root/oxycode-bot && git config user.name "OXYCODE Bot"',
    'cd /root/oxycode-bot && git add .',
    'cd /root/oxycode-bot && git commit -m "Deploy: Agent system + OpenCode integration" || echo "NOTHING_TO_COMMIT"',
    f'cd /root/oxycode-bot && git push origin main --force',
]

for cmd in commands:
    label = cmd.split('&&')[-1].strip() if '&&' in cmd else cmd
    print(f'\n> {label}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out:
        for line in out.split('\n')[:8]:
            print(f'  {line}')
    if err:
        for line in err.split('\n')[:8]:
            print(f'  ERR: {line}')

# Verify API key is set
print('\n> Checking .prod.vars for OPENCODE_API_KEY...')
stdin, stdout, stderr = ssh.exec_command('grep OPENCODE_API_KEY /root/oxycode-bot/.prod.vars')
out = stdout.read().decode().strip()
if 'OPENCODE_API_KEY' in out:
    print('  API Key is SET')
else:
    print('  API Key NOT found, setting now...')
    ssh.exec_command('echo "OPENCODE_API_KEY=YOUR_API_KEY" >> /root/oxycode-bot/.prod.vars')

ssh.close()
print('\nDone!')
