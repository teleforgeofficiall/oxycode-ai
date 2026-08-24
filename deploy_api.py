import paramiko, time, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('153.75.247.105', port=22, username='root', password='Snapbucks@Billion', timeout=15)

# Download api_server.py
stdin, stdout, stderr = ssh.exec_command('curl -sL https://files.catbox.moe/4xtzdp.py -o /root/oxycode-bot/api_server.py', timeout=30)
print('Download:', stdout.channel.recv_exit_status())

# Verify error endpoint exists
stdin, stdout, stderr = ssh.exec_command('grep -n "api/error" /root/oxycode-bot/api_server.py', timeout=10)
print('Error endpoint:', stdout.read().decode().strip())

# Restart API server
stdin, stdout, stderr = ssh.exec_command('systemctl restart oxycode-api', timeout=15)
print('Restart API:', stdout.channel.recv_exit_status())

time.sleep(3)

# Status
stdin, stdout, stderr = ssh.exec_command('systemctl is-active oxycode-api', timeout=10)
print('API status:', stdout.read().decode().strip())

# Quick test
stdin, stdout, stderr = ssh.exec_command('curl -s -X POST http://127.0.0.1:8000/api/error -H "Content-Type: application/json" -d \'{"message":"test"}\'', timeout=10)
print('Error endpoint test:', stdout.read().decode().strip())

ssh.close()
