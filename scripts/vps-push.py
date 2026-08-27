import paramiko
import os
import sys
import tarfile
sys.stdout.reconfigure(encoding='utf-8')

VPS_HOST = os.environ.get('VPS_HOST', 'YOUR_VPS_IP')
VPS_USER = os.environ.get('VPS_USER', 'root')
VPS_PASS = os.environ.get('VPS_PASS', '')
PAT = os.environ.get('GITHUB_PAT', '')
REPO_URL = f'https://teleforgeofficiall:{PAT}@github.com/teleforgeofficiall/oxycode-ai.git'
LOCAL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMP_TAR = os.path.join(os.path.dirname(LOCAL_DIR), 'oxycode-source.tar.gz')

# Files/dirs to include
INCLUDE = [
    'src', 'worker', 'vibesdk-read', 'shared', 'docs', 'scripts',
    'package.json', 'package-lock.json', 'tsconfig.json', 'tsconfig.app.json',
    'tsconfig.node.json', 'vite.config.ts', '.gitignore', 'AGENTS.md', 'CLAUDE.md', 'ARCHITECTURE.md',
    'DOCS_UPDATE_LOG.md', 'LICENSE', 'index.html', 'vercel.json',
    'screenshots', 'deploy-info.md', 'DEPLOY-README.md', 'DEPLOYMENT.md'
]

# Create tarball
print('Creating source tarball...')
with tarfile.open(TEMP_TAR, 'w:gz') as tar:
    for item in INCLUDE:
        path = os.path.join(LOCAL_DIR, item)
        if os.path.exists(path):
            tar.add(path, arcname=item)
            print(f'  Added: {item}')

tar_size = os.path.getsize(TEMP_TAR) / 1024 / 1024
print(f'  Size: {tar_size:.1f} MB')

# Connect to VPS
print('\nConnecting to VPS...')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASS, timeout=15)

# Upload tarball
print('Uploading source...')
sftp = ssh.open_sftp()
sftp.put(TEMP_TAR, '/tmp/oxycode-source.tar.gz')
sftp.close()

# Setup and push
commands = [
    ('Clone repo', f'rm -rf /tmp/oxycode-git && git clone {REPO_URL} /tmp/oxycode-git'),
    ('Extract source', 'cd /tmp/oxycode-git && tar xzf /tmp/oxycode-source.tar.gz --overwrite'),
    ('Git config', 'cd /tmp/oxycode-git && git config user.email "admin@oxycode.ai" && git config user.name "OXYCODE Bot"'),
    ('Stage all', 'cd /tmp/oxycode-git && git add .'),
    ('Commit', 'cd /tmp/oxycode-git && git commit -m "Deploy: Agent system + OpenCode integration + Security cleanup" || echo "NOTHING_TO_COMMIT"'),
    ('Push', 'cd /tmp/oxycode-git && git push origin main --force 2>&1'),
]

for label, cmd in commands:
    print(f'\n> {label}...')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out:
        for line in out.split('\n')[:10]:
            print(f'  {line}')
    if err:
        for line in err.split('\n')[:10]:
            print(f'  ERR: {line}')

# Cleanup
ssh.exec_command('rm -rf /tmp/oxycode-git /tmp/oxycode-source.tar.gz')
ssh.close()
os.remove(TEMP_TAR)
print('\nDone!')
