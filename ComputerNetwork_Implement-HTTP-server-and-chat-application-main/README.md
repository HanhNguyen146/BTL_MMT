# WeApRous — Backend (cookie session) — Assignment 1

Short: lightweight HTTP backend that supports login via a form and cookie-based access control.

## Features implemented

- POST `/login` authenticates `username=admin` / `password=password`.
  - On success: responds with index page and `Set-Cookie: auth=true; Path=/; HttpOnly`.
  - On failure: responds `401 Unauthorized`.
- GET `/`, `/index`, `/index.html`
  - If request contains cookie `auth=true` → serve `www/index.html` (200).
  - Otherwise → `401 Unauthorized`.
- Basic header parsing (Content-Length) and safe reading of POST body.
- Concurrency via threads.
- Minimal logging (server start, login result). Debug logs can be enabled in code.

## Project layout (relevant files)

- daemon/
  - httpadapter.py — main HTTP handling, login/cookie logic, reading/parsing requests.
  - request.py — Request object and cookie parsing (DEBUG flag configurable).
  - backend.py — socket listener / thread dispatch (connection log can be silenced).
- www/
  - login.html — login form used by server.
  - index.html — protected index page.
- test_cookie.py — automated tests for cookie/session flows (placed at repo root).
- tools/ (optional) — helper/test scripts used previously.

## Quick start (Windows)

1. Install dependencies:
   - Python 3.8+ and `requests` for tests:
     ```
     pip install requests
     ```
2. Start backend:
   ```
   python start_backend.py --server-ip 127.0.0.1 --server-port 9000
   ```
   Expected log: `[Backend] Listening on port 9000`

## Manual tests (curl / PowerShell)

- From PowerShell (Invoke-WebRequest differs from curl):
  - Using native curl.exe:
    ```
    curl.exe -i -X POST -d "username=admin&password=password" http://127.0.0.1:9000/login
    ```
  - Or PowerShell equivalent:
    ```
    Invoke-WebRequest -Uri "http://127.0.0.1:9000/login" -Method POST `
      -Body "username=admin&password=password" -ContentType "application/x-www-form-urlencoded" -Verbose
    ```
- Check protected resource:
  ```
  curl.exe -i --cookie "auth=true" http://127.0.0.1:9000/
  ```
- Fail case:
  ```
  curl.exe -i -X POST -d "username=bad&password=bad" http://127.0.0.1:9000/login
  ```

## Automated tests

Run the provided tests:

```
python test_cookie.py
```

- Exit code 0 = all tests passed.
- Tests cover: successful login, failed login, GET / without cookie, GET / with cookie, tampered cookie, session isolation, reuse cookie in new session, and /protected.

## How to interpret logs

- Minimal logs kept by default:
  - `[Backend] Listening on port ...`
  - `[HttpAdapter] POST /login received: content_len=... body_len=...`
  - `[HttpAdapter] POST /login parsed username=...`
- To enable verbose request debugging set `DEBUG = True` in `daemon/request.py` (will print raw request lines).

## Known limitations / notes

- Current "session" is a client-side flag `auth=true` (meets BTL requirement). For stronger correctness/security, use server-side session id + `backend.sessions` (code comments include an optional patch).
- No support for `Transfer-Encoding: chunked`.
- Static files served from `www/` only when referenced explicitly.
- Use Incognito mode to avoid browser caching/conditional GET effects during tests.

## Recommended additional checks (optional)

- Use DevTools Network tab to confirm:
  - POST request payload present.
  - Response has `Set-Cookie`.
  - Subsequent requests include cookie header.
- Use `curl.exe` or Python `requests` to avoid PowerShell `curl` alias issues.

If you want:

- I can replace `auth=true` with server-side `sessionid` storage (safer), or
- Add a `/logout` endpoint, or
- Provide a CI-style test runner.
