import paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "153.75.247.105", "root", "Snapbucks@Billion"

def run(cmd, timeout=30):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=15)
    try:
        stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        return out, err
    finally:
        c.close()

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "echo ok"
    t = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    o, e = run(cmd, t)
    print(o)
    if e.strip():
        print("[STDERR]", e)
