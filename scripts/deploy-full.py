#!/usr/bin/env python3
"""
Deploy OXYCODE AI BOT to Cloudflare Pages via VPS
Uses paramiko for SSH connection
"""

import paramiko
import os
import sys
import zipfile
import shutil
from pathlib import Path

# VPS Configuration
VPS_HOST = 'YOUR_VPS_IP'
VPS_USER = 'root'
VPS_PASSWORD = 'YOUR_VPS_PASSWORD'
VPS_DEPLOY_PATH = '/tmp/oxycode-deploy'

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DIST_DIR = PROJECT_ROOT / 'dist'
FUNCTIONS_DIR = PROJECT_ROOT / 'functions'

def connect_to_vps():
    """Establish SSH connection to VPS"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD)
        print(f"✅ Connected to VPS: {VPS_HOST}")
        return ssh
    except Exception as e:
        print(f"❌ Failed to connect to VPS: {e}")
        sys.exit(1)

def run_command(ssh, command, description=""):
    """Run a command on VPS and return output"""
    try:
        print(f"\n🔄 {description if description else 'Running command...'}")
        print(f"   Command: {command}")
        
        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode()
        error = stderr.read().decode()
        
        if output:
            print(f"   Output: {output[:500]}")
        if error:
            print(f"   Error: {error[:500]}")
            
        return output, error
    except Exception as e:
        print(f"❌ Command failed: {e}")
        return "", str(e)

def create_deploy_package():
    """Create zip package of dist and functions"""
    print("\n📦 Creating deploy package...")
    
    # Clean up if exists
    if os.path.exists('deploy-full.zip'):
        os.remove('deploy-full.zip')
    
    # Create zip file
    with zipfile.ZipFile('deploy-full.zip', 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add dist folder
        if DIST_DIR.exists():
            for root, dirs, files in os.walk(DIST_DIR):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, PROJECT_ROOT)
                    zipf.write(file_path, arcname)
                    print(f"   Added: {arcname}")
        
        # Add functions folder
        if FUNCTIONS_DIR.exists():
            for root, dirs, files in os.walk(FUNCTIONS_DIR):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, PROJECT_ROOT)
                    zipf.write(file_path, arcname)
                    print(f"   Added: {arcname}")
    
    print(f"✅ Created deploy-full.zip")
    return 'deploy-full.zip'

def deploy_to_vps(ssh, zip_file):
    """Upload and deploy to VPS"""
    print("\n📤 Uploading to VPS...")
    
    # Create temp directory
    run_command(ssh, f"rm -rf {VPS_DEPLOY_PATH}", "Cleaning up old files")
    run_command(ssh, f"mkdir -p {VPS_DEPLOY_PATH}", "Creating deploy directory")
    
    # Upload zip file
    sftp = ssh.open_sftp()
    remote_path = f"{VPS_DEPLOY_PATH}/deploy-full.zip"
    sftp.put(zip_file, remote_path)
    sftp.close()
    print(f"✅ Uploaded {zip_file} to VPS")
    
    # Extract and deploy
    run_command(ssh, f"cd {VPS_DEPLOY_PATH} && unzip -o deploy-full.zip", "Extracting files")
    
    # Deploy to Cloudflare Pages
    print("\n🚀 Deploying to Cloudflare Pages...")
    run_command(ssh, f"cd {VPS_DEPLOY_PATH} && npx wrangler pages deploy . --project-name=oxycode-miniapp --branch=main", "Deploying to CF Pages")
    
    # Cleanup
    run_command(ssh, f"rm -rf {VPS_DEPLOY_PATH}", "Cleaning up")
    
    print("\n✅ Deployment Complete!")
    print(f"🌐 URL: https://oxycode-miniapp.pages.dev")

def push_to_github(ssh):
    """Push code to GitHub from VPS"""
    print("\n📤 Pushing to GitHub...")
    
    # Navigate to project directory
    run_command(ssh, "cd /root/oxycode-bot", "Navigating to project")
    
    # Add all changes
    run_command(ssh, "git add .", "Staging changes")
    
    # Commit
    run_command(ssh, 'git commit -m "Update: Agent system integration"', "Committing changes")
    
    # Push
    run_command(ssh, "git push origin main", "Pushing to GitHub")
    
    print("\n✅ Pushed to GitHub!")

def main():
    """Main deployment function"""
    print("=" * 60)
    print("🚀 OXYCODE AI BOT - Deployment Script")
    print("=" * 60)
    
    # Step 1: Create deploy package
    zip_file = create_deploy_package()
    
    # Step 2: Connect to VPS
    ssh = connect_to_vps()
    
    try:
        # Step 3: Deploy to VPS and Cloudflare Pages
        deploy_to_vps(ssh, zip_file)
        
        # Step 4: Push to GitHub
        push_to_github(ssh)
        
        print("\n" + "=" * 60)
        print("✅ ALL DEPLOYMENTS COMPLETE!")
        print("=" * 60)
        print(f"\n🌐 Frontend: https://oxycode-miniapp.pages.dev")
        print(f"🔗 Backend: https://oxycode.duckdns.org")
        print(f"📱 Telegram: @OXYCODE_AI_BOT")
        
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
    finally:
        ssh.close()
        print("\n🔒 SSH connection closed")

if __name__ == "__main__":
    main()
