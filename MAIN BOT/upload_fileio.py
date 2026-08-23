import urllib.request, ssl, json, uuid

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

with open(r"C:\Users\Teleforge\Desktop\OXYCODE AI BOT\MAIN BOT\agent_engine.py", "rb") as f:
    data = f.read()

print(f"File size: {len(data)} bytes")

# Try catbox.moe
boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
body = (
    b"--" + boundary.encode() + b"\r\n"
    b"Content-Disposition: form-data; name=\"reqtype\"\r\n\r\n"
    b"fileupload\r\n"
    b"--" + boundary.encode() + b"\r\n"
    b"Content-Disposition: form-data; name=\"fileToUpload\"; filename=\"agent_engine.py\"\r\n"
    b"Content-Type: text/plain\r\n\r\n"
    + data + b"\r\n"
    b"--" + boundary.encode() + b"--\r\n"
)

req = urllib.request.Request("https://catbox.moe/user/api.php", data=body, method="POST")
req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
try:
    resp = urllib.request.urlopen(req, timeout=30, context=ctx)
    print("catbox URL:", resp.read().decode().strip())
except Exception as e:
    if hasattr(e, "read"):
        print(f"catbox: {e} -> {e.read()[:300]}")
    else:
        print(f"catbox: {e}")
