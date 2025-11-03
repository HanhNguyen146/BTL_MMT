import requests
import sys
import re
import time

BASE = "http://127.0.0.1:9000"
TIMEOUT = 3

def post_login(sess, username, password):
    return sess.post(f"{BASE}/login", data={"username": username, "password": password}, timeout=TIMEOUT)

def extract_cookie_from_response(r):
    sc = r.headers.get("Set-Cookie", "")
    if sc:
        m = re.search(r"(sessionid|auth)=([^;]+)", sc)
        if m:
            return {m.group(1): m.group(2)}
    # fallback to cookies in session/response
    try:
        c = r.cookies.get_dict()
        if c:
            return c
    except Exception:
        pass
    return None

def ok(msg):
    print("  -> PASS:", msg)

def fail(msg):
    print("  -> FAIL:", msg)

def run_tests():
    passed = 0
    total = 0

    print("Test 1: POST /login success (admin/password)")
    total += 1
    s = requests.Session()
    try:
        r = post_login(s, "admin", "password")
    except Exception as e:
        fail(f"request error: {e}")
        sys.exit(2)
    cookie = extract_cookie_from_response(r)
    if r.status_code == 200 and cookie:
        ok(f"200 OK and Set-Cookie present: {cookie}")
        passed += 1
    else:
        fail(f"expected 200+Set-Cookie, got status={r.status_code} headers={r.headers.get('Set-Cookie')}")
    
    print("\nTest 2: POST /login failure (wrong creds)")
    total += 1
    r2 = requests.post(f"{BASE}/login", data={"username":"x","password":"y"}, timeout=TIMEOUT)
    if r2.status_code == 401:
        ok("401 Unauthorized for bad credentials")
        passed += 1
    else:
        fail(f"expected 401, got {r2.status_code}")

    print("\nTest 3: GET / without cookie (should be 401)")
    total += 1
    r3 = requests.get(f"{BASE}/", timeout=TIMEOUT)
    if r3.status_code == 401:
        ok("401 when no cookie")
        passed += 1
    else:
        fail(f"expected 401, got {r3.status_code}")

    print("\nTest 4: GET / with cookie from successful login (session reuse)")
    total += 1
    r4 = s.get(f"{BASE}/", timeout=TIMEOUT)
    if r4.status_code == 200:
        ok("200 with login session")
        passed += 1
    else:
        fail(f"expected 200, got {r4.status_code} (cookies in session: {s.cookies.get_dict()})")

    print("\nTest 5: GET / with manual cookie header (auth or sessionid)")
    total += 1
    # try to reuse cookie value from Test1
    cookie_map = cookie or {}
    if "auth" in cookie_map:
        cstr = { "auth": cookie_map["auth"] }
    elif "sessionid" in cookie_map:
        cstr = { "sessionid": cookie_map["sessionid"] }
    else:
        cstr = {"auth":"true"}  # best-effort
    r5 = requests.get(f"{BASE}/", cookies=cstr, timeout=TIMEOUT)
    if r5.status_code == 200:
        ok(f"200 with manual cookie {cstr}")
        passed += 1
    else:
        fail(f"expected 200 with manual cookie {cstr}, got {r5.status_code}")

    print("\nTest 6: Tampered cookie should not grant access (auth=false or bad sessionid)")
    total += 1
    tampered = {}
    if "auth" in cookie_map:
        tampered = {"auth": "false"}
    elif "sessionid" in cookie_map:
        tampered = {"sessionid": cookie_map.get("sessionid","")+ "bad"}
    else:
        tampered = {"auth": "false"}
    r6 = requests.get(f"{BASE}/", cookies=tampered, timeout=TIMEOUT)
    if r6.status_code == 401:
        ok("401 with tampered cookie")
        passed += 1
    else:
        fail(f"expected 401 with tampered cookie, got {r6.status_code}")

    print("\nTest 7: Multiple sessions isolation (s1 logged in, s2 not)")
    total += 1
    s1 = requests.Session()
    s2 = requests.Session()
    s1.post(f"{BASE}/login", data={"username":"admin","password":"password"}, timeout=TIMEOUT)
    r_s1 = s1.get(f"{BASE}/", timeout=TIMEOUT)
    r_s2 = s2.get(f"{BASE}/", timeout=TIMEOUT)
    if r_s1.status_code == 200 and r_s2.status_code == 401:
        ok("session isolation OK (s1=200, s2=401)")
        passed += 1
    else:
        fail(f"expected s1=200 and s2=401, got s1={r_s1.status_code} s2={r_s2.status_code}")

    print("\nTest 8: Reuse Set-Cookie in a new Session instance")
    total += 1
    # build new session with cookie extracted from Test1
    if cookie_map:
        new_s = requests.Session()
        for k,v in cookie_map.items():
            new_s.cookies.set(k, v, domain="127.0.0.1", path="/")
        r_new = new_s.get(f"{BASE}/", timeout=TIMEOUT)
        if r_new.status_code == 200:
            ok("new session with copied cookie => 200")
            passed += 1
        else:
            fail(f"expected 200, got {r_new.status_code}")
    else:
        fail("no cookie from login to reuse")
    
    print("\nTest 9: /protected status when logged in (informational)")
    total += 1
    r_prot = s.get(f"{BASE}/protected", timeout=TIMEOUT)
    if r_prot.status_code == 200:
        ok("/protected returned 200 when logged in")
        passed += 1
    else:
        fail(f"/protected returned {r_prot.status_code} when logged in")

    print(f"\nSummary: {passed}/{total} checks passed")
    if passed != total:
        sys.exit(1)
    print("All required cookie/session tests passed.")
    sys.exit(0)

if __name__ == "__main__":
    try:
        run_tests()
    except requests.exceptions.ConnectionError as e:
        print("Connection error: is backend running on", BASE, "?")
        print(e)
        sys.exit(2)
    except Exception as e:
        print("Error during tests:", e)
        sys.exit(3)