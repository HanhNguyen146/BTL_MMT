from .session_store import get_user_from_session

def auth_from_cookie_header(cookie_header):
    """
    cookie_header: string như "k1=v1; sessionid=abc123; ..."
    Trả về username (str) hoặc None.
    """
    cookies = {}
    if cookie_header:
        for pair in cookie_header.split(';'):
            if '=' in pair:
                k, v = pair.strip().split('=', 1)
                cookies[k] = v
    sessionid = cookies.get('sessionid')
    if not sessionid:
        return None
    return get_user_from_session(sessionid)