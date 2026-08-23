import urllib.request, urllib.parse, json, ssl, http.cookiejar

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

api_key = "jd7RSUUfqQjOxTNZyPu7AjTxSB7xdvJH"
base = "https://153.75.247.105:39928"
entrance = "4496725b"

# Cookie jar for session
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(
    urllib.request.HTTPSHandler(context=ctx),
    urllib.request.HTTPCookieProcessor(cj)
)

# Step 1: Login to get BT session cookie
login_url = f"{base}/{entrance}/login"
login_data = urllib.parse.urlencode({
    "username": "xpqntifw",
    "password": ""
}).encode()

# Try various login approaches
print("=== Trying login ===")

# Method 1: POST login with apikey
for password_attempt in [""]:
    login_payload = json.dumps({"username": "xpqntifw", "password": password_attempt})
    req = urllib.request.Request(
        f"{base}/{entrance}/login",
        data=login_payload.encode(),
        headers={
            "Content-Type": "application/json",
            "apikey": api_key
        },
        method="POST"
    )
    try:
        resp = opener.open(req, timeout=10)
        data = resp.read().decode()
        print(f"Login response: {data[:500]}")
        break
    except Exception as e:
        if hasattr(e, "read"):
            body = e.read()[:300].decode(errors="replace")
            print(f"Login error: {e} -> {body}")
        else:
            print(f"Login error: {e}")

# Step 2: Check what cookies we got
print("\n=== Cookies ===")
for cookie in cj:
    print(f"  {cookie.name} = {cookie.value[:50]}...")

# Step 3: Try API call with session
print("\n=== API call ===")
for path in [f"{entrance}/system", f"{entrance}/api/system", "system"]:
    url = f"{base}/{path}?action=GetSystemTotal"
    req = urllib.request.Request(url, headers={"apikey": api_key})
    try:
        resp = opener.open(req, timeout=10)
        data = resp.read().decode()
        print(f"OK with {path}: {data[:300]}")
        break
    except Exception as e:
        if hasattr(e, "read"):
            body = e.read()[:200].decode(errors="replace")
            print(f"{path}: {e} -> {body}")
        else:
            print(f"{path}: {e}")
