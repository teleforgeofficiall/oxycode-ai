import paramiko
import sys

VPS = ('153.75.247.105', 'root', 'Snapbucks@Billion')
LOCAL_API = r"C:\Users\Teleforge\Desktop\OXYCODE AI BOT\MAIN BOT\api_server.py"
REMOTE_API = "/root/oxycode-bot/api_server.py"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS[0], username=VPS[1], password=VPS[2])

def run(cmd, timeout=60):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    return out.strip(), err.strip()

# 1. Backup current remote api_server.py
out, err = run(f"cp {REMOTE_API} {REMOTE_API}.bak.$(date +%Y%m%d%H%M%S) && ls -la /root/oxycode-bot/api_server.py.bak.* | tail -3")
print("[backup]", out or err)

# 2. Upload new api_server.py via SFTP
sftp = ssh.open_sftp()
sftp.put(LOCAL_API, REMOTE_API)
st = sftp.stat(REMOTE_API)
print(f"[upload] ok size={st.st_size}")
sftp.close()

# 3. Syntax-check remotely
out, err = run("cd /root/oxycode-bot && python3 -m py_compile api_server.py && echo COMPILE_OK")
print("[compile]", out or err)
if "COMPILE_OK" not in out:
    print("FARZI: compile failed, aborting"); sys.exit(1)

# 4. Inspect nginx conf for the oxycode site / ws location
out, err = run("grep -rl 'oxycode' /etc/nginx/sites-enabled/ /etc/nginx/conf.d/ 2>/dev/null")
print("[nginx files]", out)
for f in out.splitlines():
    out2, _ = run(f"cat {f}")
    print(f"----- {f} -----")
    print(out2[:3000])

# 5. Restart API service
out, err = run("systemctl restart oxycode-api && sleep 2 && systemctl is-active oxycode-api")
print("[restart]", out or err)

# 6. Quick health check
out, err = run("curl -s -m 10 http://localhost:8000/api/status")
print("[health]", out or err)

# 7. Test OpenCode LLM from VPS
payload = '{"model":"mimo-v2.5-free","messages":[{"role":"system","content":"You are OXYGENT."},{"role":"user","content":"hey"}],"stream":false}'
cmd = (
    "curl -s -m 45 -X POST https://opencode.ai/inference/openai/v1/chat/completions "
    "-H 'Content-Type: application/json' -H 'User-Agent: opencode/1.18.16' "
    "-d '" + payload + "'"
)
out, err = run(cmd, timeout=60)
print("[llm-test] response head:", out[:600])
if not out:
    print("[llm-test] EMPTY RESPONSE, stderr:", err[:300])

ssh.close()
print("DEPLOY DONE")
