import sys, jwt, urllib.request, json
sys.path.insert(0, "/root/oxycode-bot")
from dotenv import load_dotenv
load_dotenv("/root/oxycode-bot/.env")

ADMIN_TOKEN = jwt.encode({"sub": "8972944701"}, "oxycode-secret-change-this-in-production", algorithm="HS256")
req = urllib.request.Request("http://127.0.0.1:8000/api/admin/maintenance/toggle", 
    headers={"Authorization": f"Bearer {ADMIN_TOKEN}"}, method="POST")
with urllib.request.urlopen(req, timeout=15) as resp:
    print(json.loads(resp.read()))
# Check status
req2 = urllib.request.Request("http://127.0.0.1:8000/api/status")
with urllib.request.urlopen(req2, timeout=10) as resp2:
    print(json.loads(resp2.read()))
