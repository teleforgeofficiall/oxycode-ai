import paramiko

VPS_HOST = "153.75.247.105"
VPS_USER = "root"
VPS_PASS = "Snapbucks@Billion"

def run(ssh, cmd, timeout=30):
    print(f"  > {cmd[:120]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(f"  OUT: {out[:500]}")
    if err:
        lines = [l for l in err.split('\n') if l.strip()]
        if lines:
            print(f"  ERR: {'; '.join(lines)[:300]}")
    return out, err

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASS, timeout=15)
    print("Connected!\n")

    # Test locally via 127.0.0.1
    print("=== Local API health ===")
    run(ssh, "curl -s http://127.0.0.1:8000/api/health")
    
    print("\n=== Local API auth check ===")
    run(ssh, "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/user/me")
    
    print("\n=== SSL cert expiry ===")
    run(ssh, "echo | timeout 5 openssl s_client -connect 127.0.0.1:443 -servername oxycode.duckdns.org 2>/dev/null | openssl x509 -noout -dates 2>/dev/null")
    
    print("\n=== nginx listening ===")
    run(ssh, "ss -tlnp | grep -E ':80|:443'")
    
    print("\n=== API service status ===")
    run(ssh, "systemctl status oxycode-api --no-pager | head -10")

    ssh.close()
    print("\n=== DONE ===")

if __name__ == "__main__":
    main()
