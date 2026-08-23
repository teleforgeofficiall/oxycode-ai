"""Quick upload helper - run this to upload agent_engine.py via VPS API"""
import paramiko
import sys

VPS_HOST = "153.75.247.105"
VPS_USER = "root"
VPS_PASS = "Snapbucks@Billion"
LOCAL_FILE = r"C:\Users\Teleforge\Desktop\OXYCODE AI BOT\MAIN BOT\agent_engine.py"
REMOTE_FILE = "/root/oxycode-bot/agent_engine.py"

# Try multiple ports
for port in [22, 2222, 2200, 8022]:
    try:
        print(f"[*] Trying port {port}...")
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(VPS_HOST, port=port, username=VPS_USER, password=VPS_PASS, timeout=10)
        print(f"[+] Connected on port {port}!")
        
        sftp = c.open_sftp()
        sftp.put(LOCAL_FILE, REMOTE_FILE)
        print(f"[+] Uploaded {LOCAL_FILE} -> {REMOTE_FILE}")
        
        stdin, stdout, stderr = c.exec_command("systemctl restart oxycode-bot oxycode-api")
        print("[+] Restarted services")
        print(stdout.read().decode())
        c.close()
        sys.exit(0)
    except Exception as e:
        print(f"[-] Port {port} failed: {e}")
        continue

print("[!] All ports failed. Use hosting panel console instead.")
