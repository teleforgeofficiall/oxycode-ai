import paramiko, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

IP='153.75.247.105'; USER='root'; PASS='Snapbucks@Billion'
LOCAL=r'C:\Users\Teleforge\Desktop\OXYCODE AI BOT\CLONE BOT'
REMOTE='/root/oxygent-clone'

ssh=paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(IP, username=USER, password=PASS, timeout=10)
sftp=ssh.open_sftp()

sftp.put(os.path.join(LOCAL, 'database.py'), f"{REMOTE}/database.py")
print("Uploaded database.py")

sftp.close()

# Clear cache and restart
stdin, stdout, stderr = ssh.exec_command("rm -rf /root/oxygent-clone/__pycache__ && pm2 restart oxygent-clone")
print(stdout.read().decode('utf-8', errors='replace'))

import time; time.sleep(4)
stdin, stdout, stderr = ssh.exec_command("pm2 logs oxygent-clone --lines 3 --nostream")
print(stdout.read().decode('utf-8', errors='replace'))

ssh.close()
print("Done!")
