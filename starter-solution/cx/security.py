"""Synthetic authentication, server-side sessions, and deterministic policy."""
import json
import secrets
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import config
from .telemetry import emit

_SESSIONS = {}
_LOCK = threading.RLock()


class ServiceFault(Exception):
    def __init__(self, code, message="The requested service could not verify the information"):
        self.code = str(code)
        super().__init__(message)


def _call_auth(username, password):
    req = Request(config.API_BASE + "/api/auth/login", data=json.dumps({"username": username, "password": password}).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=config.REQUEST_TIMEOUT) as r: return r.status, json.loads(r.read(8192))
    except HTTPError as e:
        try: return e.code, json.loads(e.read(4096))
        except Exception: return e.code, {}
    except (URLError, TimeoutError) as e: raise ServiceFault("auth_unavailable", "Authentication service is unavailable") from e


def login(username, password, trace_id):
    emit("authentication.attempted", trace_id, component="auth")
    status, result = _call_auth(str(username)[:100], str(password)[:200])
    expires = int(result.get("expiresIn", 0)) if isinstance(result, dict) else 0
    if status != 200 or not result.get("customerId") or not result.get("accessToken") or expires <= 0:
        emit("authentication.failed", trace_id, status="failure", component="auth", metadata={"status": status})
        raise ServiceFault("invalid_or_expired", "Invalid credentials or expired authentication")
    # The bearer token is deliberately not retained: the supplied APIs do not require it.
    sid = secrets.token_urlsafe(32)
    state = {"customer_id": result["customerId"], "account_id": result.get("accountId"),
             "roles": list(result.get("roles", [])), "expires_at": time.time() + expires,
             "pending": None, "turns": 0, "created_at": time.time()}
    with _LOCK: _SESSIONS[sid] = state
    state["session_id"] = sid
    emit("authentication.succeeded", trace_id, sid, "auth", metadata={"customerId": state["customer_id"], "roles": state["roles"]})
    return sid, state


def anonymous_session():
    sid = secrets.token_urlsafe(32)
    state = {"customer_id": None, "account_id": None, "roles": [], "expires_at": time.time()+config.SESSION_TTL_SECONDS,
             "pending": None, "turns": 0, "created_at": time.time(), "session_id": sid}
    with _LOCK: _SESSIONS[sid] = state
    return sid, state


def session(sid, trace_id=None):
    if not sid: return None
    with _LOCK: state = _SESSIONS.get(sid)
    if not state: return None
    if state["expires_at"] <= time.time():
        with _LOCK: _SESSIONS.pop(sid, None)
        if trace_id: emit("authentication.failed", trace_id, sid, "auth", "denied", metadata={"reason": "expired"})
        return None
    return state


def logout(sid):
    with _LOCK: _SESSIONS.pop(sid, None)


def authorize(state, account_id, trace_id, protected=True):
    if protected and not state:
        emit("authorization.denied", trace_id, component="authorization", status="denied", metadata={"reason": "authentication_required"})
        raise ServiceFault("unauthorized", "Please sign in to access protected information")
    if not state: return True
    if "support-agent" in state["roles"]:
        emit("authorization.allowed",trace_id,state.get("session_id","session"),"authorization",metadata={"resourceType":"account","role":"support-agent"})
        return True
    if account_id and account_id != state.get("account_id"):
        emit("authorization.denied", trace_id, component="authorization", status="denied", metadata={"resource": account_id})
        raise ServiceFault("forbidden", "You may only access your own account")
    emit("authorization.allowed", trace_id, state.get("session_id", "session"), "authorization", metadata={"resourceType": "account"})
    return True


def require_support(state, trace_id):
    if not state or "support-agent" not in state.get("roles", []):
        emit("authorization.denied", trace_id, component="authorization", status="denied", metadata={"resourceType": "operations"})
        raise ServiceFault("forbidden", "Support-agent access is required")
    emit("authorization.allowed",trace_id,state.get("session_id","session"),"authorization",metadata={"resourceType":"operations"})


def session_count():
    with _LOCK: return len(_SESSIONS)
