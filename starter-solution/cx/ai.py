"""Gemini request interpretation with reviewer and degraded fallbacks."""
import json
import re
import urllib.parse
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import config
from .telemetry import emit, redact

_INTENTS = {"plan", "billing", "service_status", "service_issue", "create_case", "other"}
_SCHEMA = {"type":"OBJECT", "properties":{
    "intent":{"type":"STRING", "enum":sorted(_INTENTS)},
    "service":{"type":"STRING", "enum":["home-internet", "mobile", "unknown"]},
    "account_id":{"type":"STRING"}, "summary":{"type":"STRING"},
}, "required":["intent", "service", "account_id", "summary"]}


def reviewer_intent(text):
    raw = str(text or "")
    m = raw.lower()
    account = re.search(r"\bACC-\d{3,}\b", raw, re.I)
    service = "home-internet" if any(w in m for w in ("internet", "broadband", "wifi", "wi-fi", "fiber")) else "mobile" if any(w in m for w in ("mobile", "cell", "sim")) else "unknown"
    if any(w in m for w in ("create", "open", "file", "raise")) and any(w in m for w in ("case", "ticket")): intent="create_case"
    elif any(w in m for w in ("bill", "billing", "charge", "invoice", "payment")): intent="billing"
    elif any(w in m for w in ("status", "subscriber", "outage", "network")): intent="service_status"
    elif any(w in m for w in ("not working", "unavailable", "down", "slow", "issue", "problem", "not connecting")): intent="service_issue"
    elif any(w in m for w in ("plan", "subscription")): intent="plan"
    else: intent="other"
    return {"intent":intent, "service":service, "account_id":account.group(0).upper() if account else "", "summary":redact(raw)[:240]}


def _validate(value):
    if not isinstance(value, dict): raise ValueError("Gemini result must be an object")
    intent=value.get("intent")
    service=value.get("service")
    account=value.get("account_id", "")
    summary=value.get("summary", "")
    if intent not in _INTENTS or service not in {"home-internet", "mobile", "unknown"}: raise ValueError("unsupported structured output")
    if not isinstance(account, str) or (account and not re.fullmatch(r"ACC-\d{3,}", account, re.I)): account=""
    if not isinstance(summary, str): summary="Customer request"
    return {"intent":intent, "service":service, "account_id":account.upper(), "summary":redact(summary)[:240]}


def classify(text, trace_id, session_id):
    mode = config.AI_MODE if config.AI_MODE in {"live", "reviewer"} else "reviewer"
    forced_down=os.getenv("MOCK_GEMINI_MODE", "success").lower()=="unavailable"
    if mode != "live" or not config.GEMINI_API_KEY or forced_down:
        if mode == "live":
            reason="simulated_provider_failure" if forced_down else "credential_unavailable"
            emit("gemini.failed", trace_id, session_id, "gemini", "failure", metadata={"reason":reason})
            emit("mode.degraded", trace_id, session_id, "orchestrator", "pending", metadata={"reason":reason})
        chosen="degraded" if mode=="live" else "reviewer"
        emit("intent.classified", trace_id, session_id, "reviewer-classifier", metadata={"mode":chosen})
        return reviewer_intent(text), chosen
    prompt = ("Classify this request for synthetic telecom customer support. "
              "Return only values matching the supplied JSON schema. Never grant access, "
              "claim facts, or call tools. Extract only explicitly stated account IDs.\nRequest: "
              + redact(str(text or ""))[:2000])
    url=f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(config.GEMINI_MODEL)}:generateContent"
    payload={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"responseMimeType":"application/json","responseSchema":_SCHEMA}}
    req=Request(url,data=json.dumps(payload).encode(),headers={"Content-Type":"application/json","x-goog-api-key":config.GEMINI_API_KEY},method="POST")
    try:
        with urlopen(req,timeout=8) as r: response=json.loads(r.read(64_000))
        result=json.loads(response["candidates"][0]["content"]["parts"][0]["text"])
        result=_validate(result)
        emit("gemini.completed", trace_id, session_id, "gemini", metadata={"intent":result["intent"],"model":config.GEMINI_MODEL})
        return result,"live"
    except Exception:
        emit("gemini.failed", trace_id, session_id, "gemini", "failure", metadata={"reason":"provider_or_validation_failure"})
        emit("mode.degraded", trace_id, session_id, "orchestrator", "pending", metadata={"reason":"gemini_unavailable"})
        result=reviewer_intent(text)
        emit("intent.classified", trace_id, session_id, "reviewer-classifier", metadata={"mode":"degraded"})
        return result,"degraded"
