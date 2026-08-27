#!/usr/bin/env python3
"""Push to GitHub with PAT token"""

import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('YOUR_VPS_IP', username='root', password='YOUR_VPS_PASSWORD')

PAT = 'YOUR_GITHUB_PAT'
REPO_URL = 'https://teleforgeofficiall:' + PAT + '@github.com/teleforgeofficiall/oxycode-ai.git'

cmd = (
    'cd /root/oxycode-ai && '
    'git remote set-url origin ' + REPO_URL + ' && '
    'git push origin main'
)

stdin, stdout, stderr = ssh.exec_command(cmd)
output = stdout.read().decode()
error = stderr.read().decode()
if output:
    print(output)
if error:
    print(error)

ssh.close()
print("Done!")
