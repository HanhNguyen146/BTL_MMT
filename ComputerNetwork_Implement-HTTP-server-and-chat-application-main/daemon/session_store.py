import threading
import time
import uuid
from typing import Optional

# Simple in-memory session store with TTL and thread-safety.
# API:
#   create_session(username, ttl=3600) -> sessionid (str)
#   get_user_from_session(sessionid) -> username | None
#   destroy_session(sessionid) -> None
#   refresh_session(sessionid, ttl=3600) -> bool

_lock = threading.RLock()
_sessions = {}  # sessionid -> (username, expires_at)


def _now() -> float:
    return time.time()


def _cleanup_expired() -> None:
    """Remove expired sessions (called on accesses)."""
    with _lock:
        now = _now()
        expired = [sid for sid, (_, exp) in _sessions.items() if exp <= now]
        for sid in expired:
            del _sessions[sid]


def create_session(username: str, ttl: int = 3600) -> str:
    """Create a session for username. Returns session id string."""
    sid = uuid.uuid4().hex
    expires_at = _now() + int(ttl)
    with _lock:
        _sessions[sid] = (username, expires_at)
    return sid


def get_user_from_session(sessionid: str) -> Optional[str]:
    """Return username for sessionid or None if missing/expired."""
    if not sessionid:
        return None
    with _lock:
        _cleanup_expired()
        entry = _sessions.get(sessionid)
        if not entry:
            return None
        username, _ = entry
        return username


def destroy_session(sessionid: str) -> None:
    """Delete a session if present."""
    with _lock:
        _sessions.pop(sessionid, None)


def refresh_session(sessionid: str, ttl: int = 3600) -> bool:
    """Extend TTL for a session. Returns True if session existed."""
    with _lock:
        entry = _sessions.get(sessionid)
        if not entry:
            return False
        username, _ = entry
        _sessions[sessionid] = (username, _now() + int(ttl))
        return True