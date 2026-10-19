"""Schema-checked, redacted workflow events and derived operational metrics."""
import datetime as dt
import hashlib
import json
import re
import threading
import time
import uuid
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVENTS_FILE = ROOT / "starter-solution" / "events.jsonl"
_LOCK = threading.RLock()
_EVENTS = []
_STARTED = {}
_SENSITIVE = re.compile(r"(?i)(password|passcode|token|api[_ -]?key|secret)\s*(?:[:=]|is)\s*\S+")
_BEARER = re.compile(r"(?i)\bBearer\s+\S+")
_EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_PHONE = re.compile(r"\b(?:\+?\d[\d ()-]{7,}\d)\b")
_ALLOWED_STATUS = {"success", "failure", "pending", "denied"}


def _session_reference(session_id):
    """Return a stable, non-reversible reference instead of a cookie value."""
    value = str(session_id or "system")
    if value == "system":
        return value
    return "sess-" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def redact(value):
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if any(x in str(k).lower() for x in ("password", "token", "secret", "credential", "cookie", "api_key", "idempotency")) else redact(v)) for k, v in value.items()}
    if isinstance(value, list): return [redact(v) for v in value]
    if isinstance(value, str):
        value = _BEARER.sub("Bearer [REDACTED]", _SENSITIVE.sub(r"\1=[REDACTED]", value))
        return _PHONE.sub("[PHONE]", _EMAIL.sub("[EMAIL]", value))[:500]
    return value


def emit(event_type, trace_id, session_id="system", component="orchestrator", status="success", duration_ms=None, metadata=None):
    if event_type == "request.received": _STARTED[trace_id]=time.perf_counter()
    if duration_ms is None and event_type.startswith("workflow.") and trace_id in _STARTED:
        duration_ms=(time.perf_counter()-_STARTED.pop(trace_id))*1000
    event = {"eventId": "EVT-" + uuid.uuid4().hex[:12], "traceId": trace_id,
             "sessionId": _session_reference(session_id), "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
             "eventType": event_type, "component": component, "status": status}
    if duration_ms is not None: event["durationMs"] = max(0, round(float(duration_ms), 2))
    if metadata: event["metadata"] = redact(metadata)
    if not event["traceId"] or status not in _ALLOWED_STATUS: return None
    with _LOCK:
        _EVENTS.append(event)
        try:
            EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with EVENTS_FILE.open("a", encoding="utf-8") as f: f.write(json.dumps(event) + "\n")
        except OSError:
            # Telemetry storage failure must not fail a customer workflow.
            pass
    return event


def trace(trace_id):
    with _LOCK: return [e for e in _EVENTS if e["traceId"] == trace_id]


def recent_traces(limit=50):
    with _LOCK: items = list(_EVENTS)
    result = {};seen=set()
    for e in reversed(items):
        if e["traceId"] not in result:
            if len(result)>=limit: break
            result[e["traceId"]]=[];seen.add(e["traceId"])
        result[e["traceId"]].append(e)
    return [{"traceId": key, "events": list(reversed(rows))} for key, rows in result.items()]


def metrics():
    with _LOCK: events = list(_EVENTS)
    by_trace = {}
    for e in events: by_trace.setdefault(e["traceId"], []).append(e)
    requests = [v for v in by_trace.values() if any(e["eventType"] == "request.received" for e in v)]
    types = Counter(e["eventType"] for e in events)
    finals = [next((e["eventType"] for e in reversed(v) if e["eventType"].startswith("workflow.")), "workflow.pending") for v in requests]
    total = len(requests)
    tool = [e for e in events if e["eventType"] in {"tool.completed", "tool.failed"}]
    resolved = sum(x == "workflow.resolved" for x in finals)
    escalated = sum(any(e["eventType"]=="escalation.created" for e in v) for v in requests)
    failures_by={}
    for e in events:
        if e["eventType"]=="tool.failed":
            tool_name=e.get("metadata",{}).get("tool",e["component"]);failures_by[tool_name]=failures_by.get(tool_name,0)+1
    failed_traces=sum(any(e["eventType"]=="tool.failed" for e in v) for v in requests)
    durations=[e["durationMs"] for e in events if e["eventType"].startswith("workflow.") and "durationMs" in e]
    gemini_durations=[e["durationMs"] for e in events if e["eventType"] in {"gemini.completed", "gemini.failed"} and "durationMs" in e]
    return {"totalSessions": len({e["sessionId"] for e in events if e["sessionId"] != "system"}),
            "totalRequests": total, "resolved": resolved, "escalations": escalated,
            "resolutionRate": round(resolved / total, 3) if total else 0,
            "escalationRate": round(escalated / total, 3) if total else 0,
            "failureRate": round(failed_traces/total,3) if total else 0,
            "averageWorkflowDurationMs": round(sum(durations)/len(durations),1) if durations else 0,
            "averageGeminiLatencyMs": round(sum(gemini_durations)/len(gemini_durations),1) if gemini_durations else 0,
            "failuresByIntegration": failures_by,
            "toolCallSuccessRate": round(sum(e["status"] == "success" for e in tool) / len(tool), 3) if tool else 0,
            "authenticationFailures": types["authentication.failed"], "authorizationDenials": types["authorization.denied"],
            "geminiCalls": types["gemini.completed"], "geminiFailures": types["gemini.failed"],
            "retryCount": types["retry.performed"], "totalEvents": len(events)}


def reset():
    with _LOCK: _EVENTS.clear();_STARTED.clear()
