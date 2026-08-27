#!/usr/bin/env python3
"""Push agent system files to GitHub via VPS"""

import paramiko
import os

VPS_HOST = 'YOUR_VPS_IP'
VPS_USER = 'root'
VPS_PASSWORD = 'YOUR_VPS_PASSWORD'
PROJECT_ROOT = r'C:\Users\Teleforge\Desktop\OXYCODE AI BOT'

FILES_TO_UPLOAD = [
    'worker/agents/types.ts',
    'worker/agents/intentDetector.ts',
    'worker/agents/mainAgent.ts',
    'worker/agents/plannerAgent.ts',
    'worker/agents/buildAgent.ts',
    'worker/agents/exploreAgent.ts',
    'worker/agents/debugAgent.ts',
    'worker/agents/subAgentManager.ts',
    'worker/agents/index.ts',
    'worker/api/controllers/agent/agentSystemController.ts',
    'worker/api/routes/codegenRoutes.ts',
    'src/routes/chat/components/plan-display.tsx',
    'src/routes/chat/components/plan-modify.tsx',
    'src/routes/chat/components/confirmation-dialog.tsx',
    'src/routes/chat/components/agent-progress.tsx',
    'src/routes/chat/components/deploy-status.tsx',
    'src/routes/chat/components/agent-system-wrapper.tsx',
    'src/routes/chat/hooks/use-agent-system.ts',
]

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD)
    print(f"Connected to VPS: {VPS_HOST}")

    sftp = ssh.open_sftp()

    for file_path in FILES_TO_UPLOAD:
        local_path = os.path.join(PROJECT_ROOT, file_path)
        remote_path = f'/root/oxycode-ai/{file_path}'

        remote_dir = os.path.dirname(remote_path)
        ssh.exec_command(f'mkdir -p {remote_dir}')

        try:
            sftp.put(local_path, remote_path)
            print(f"Uploaded: {file_path}")
        except Exception as e:
            print(f"Error uploading {file_path}: {e}")

    sftp.close()

    # Git add, commit, push
    cmd = 'cd /root/oxycode-ai && git add . && git commit -m "feat: Add multi-agent system with planner, build, explore, debug agents" && git push origin main'
    stdin, stdout, stderr = ssh.exec_command(cmd)
    output = stdout.read().decode()
    error = stderr.read().decode()
    if output:
        print(output)
    if error:
        print(error)

    ssh.close()
    print("Done!")

if __name__ == "__main__":
    main()
