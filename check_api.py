import paramiko

VPS_HOST = "153.75.247.105"
VPS_USER = "root"
VPS_PASS = "Snapbucks@Billion"

def run(ssh, cmd, timeout=15):
    print(f"  > {cmd[:150]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    try:
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
    except:
        out = "(timeout)"
        err = "(timeout)"
    if out:
        print(f"  OUT: {out[:600]}")
    if err:
        lines = [l for l in err.split('\n') if l.strip()]
        if lines:
            print(f"  ERR: {'; '.join(lines)[:400]}")
    return out, err

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASS, timeout=15)
    print("Connected!\n")

    print("=== Service status ===")
    run(ssh, "systemctl is-active oxycode-api")
    
    print("\n=== Last 20 log lines ===")
    run(ssh, "journalctl -u oxycode-api --no-pager -n 20")
    
    print("\n=== Process check ===")
    run(ssh, "ps aux | grep -i 'uvicorn\\|python.*api_server' | grep -v grep")
    
    print("\n=== Port check ===")
    run(ssh, "ss -tlnp | grep 8000")
    
    print("\n=== Try curl with timeout ===")
    run(ssh, "curl -s --max-time 5 http://127.0.0.1:8000/api/health 2>&1 || echo 'FAILED'")

    ssh.close()
    print("\n=== DONE ===")

if __name__ == "__main__":
    main()
