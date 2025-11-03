from .session_store import create_session

def handle_login(username):
    """
    Sau khi xác thực username/password thành công,
    trả về (status, headers, body) cho server HTTP dùng.
    """
    sid = create_session(username, ttl=3600)
    headers = {
        "Set-Cookie": f"sessionid={sid}; HttpOnly; Path=/; Max-Age=3600",
        "Content-Type": "text/plain; charset=utf-8",
    }
    body = b"Login OK"
    status = "200 OK"
    return status, headers, body