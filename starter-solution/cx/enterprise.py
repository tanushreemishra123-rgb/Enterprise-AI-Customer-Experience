"""Narrow adapters for the supplied REST services and legacy XML contract."""
import json
import time
import urllib.parse
from defusedxml import ElementTree as ET
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import config
from .security import ServiceFault
from .telemetry import emit


def request(method, path, body=None, timeout=None, xml=False, trace_id="", tool="enterprise"):
    emit("tool.invoked", trace_id, component=tool, metadata={"tool": tool})
    data = body.encode() if isinstance(body, str) else (json.dumps(body).encode() if body is not None else None)
    headers = {"Accept": "application/xml" if xml else "application/json"}
    if data is not None: headers["Content-Type"] = "application/xml" if xml else "application/json"
    req = Request(config.API_BASE + path, data=data, headers=headers, method=method)
    attempts=(config.MAX_RETRIES+1) if method=="GET" else 1
    for attempt in range(attempts):
        try:
            with urlopen(req, timeout=timeout or config.REQUEST_TIMEOUT) as r:
                raw = r.read(100_000)
                result = raw.decode("utf-8", "replace") if xml else json.loads(raw)
                emit("tool.completed", trace_id, component=tool, metadata={"tool": tool, "httpStatus": r.status})
                return result
        except HTTPError as e:
            if e.code == 409:
                try:
                    duplicate = json.loads(e.read(4096))
                    if duplicate.get("caseId"):
                        emit("tool.completed", trace_id, component=tool, metadata={"tool": tool, "duplicate": True})
                        return {"caseId": duplicate["caseId"], "status": "open", "duplicate": True}
                except Exception: pass
            if method=="GET" and e.code in {429,502,503,504} and attempt+1<attempts:
                emit("retry.performed",trace_id,component=tool,status="pending",metadata={"tool":tool,"attempt":attempt+2})
                time.sleep(min(.1*(2**attempt),.5));continue
            emit("tool.failed", trace_id, component=tool, status="failure", metadata={"tool": tool, "httpStatus": e.code})
            raise ServiceFault(str(e.code), f"{tool} returned HTTP {e.code}") from e
        except (URLError, TimeoutError, json.JSONDecodeError) as e:
            if method=="GET" and attempt+1<attempts:
                emit("retry.performed",trace_id,component=tool,status="pending",metadata={"tool":tool,"attempt":attempt+2})
                time.sleep(min(.1*(2**attempt),.5));continue
            emit("tool.failed", trace_id, component=tool, status="failure", metadata={"tool": tool, "reason": "timeout_or_malformed"})
            raise ServiceFault("unavailable", f"{tool} timed out or returned invalid data") from e


def account(account_id, trace_id):
    result = request("GET", "/api/accounts/" + urllib.parse.quote(account_id, safe=""), trace_id=trace_id, tool="account-service")
    if not isinstance(result, dict) or result.get("accountId") != account_id or not isinstance(result.get("services"), list) or not isinstance(result.get("plan"), dict):
        raise ServiceFault("malformed", "Account response failed validation")
    return result


def billing(account_id, trace_id):
    result = request("GET", f"/api/accounts/{urllib.parse.quote(account_id, safe='')}/billing", trace_id=trace_id, tool="billing-service")
    if not isinstance(result, dict) or result.get("accountId") != account_id or not isinstance(result.get("total"), (int, float)) or not result.get("period"):
        raise ServiceFault("malformed", "Billing response failed validation")
    return result


def customer(customer_id, trace_id):
    result = request("GET", "/api/customers/" + urllib.parse.quote(customer_id, safe=""), trace_id=trace_id, tool="customer-profile")
    if not isinstance(result, dict) or result.get("customerId") != customer_id:
        raise ServiceFault("malformed", "Customer response failed validation")
    return result


def outage(postal_code, trace_id):
    result = request("GET", "/api/network/outages?postalCode=" + urllib.parse.quote(postal_code, safe=""), trace_id=trace_id, tool="network-outage")
    if not isinstance(result, dict) or result.get("postalCode") != postal_code or result.get("status") not in {"normal", "degraded", "down", "unknown"}:
        raise ServiceFault("malformed", "Network status response failed validation")
    return result


def legacy(account_record, trace_id):
    services = account_record.get("services") or []
    if not services or not services[0].get("serviceId"): raise ServiceFault("missing_service", "No service identifier was returned")
    acct = account_record["accountId"]
    service_id = services[0]["serviceId"]
    body = (f"<SubscriberStatusRequest><AccountNumber>{acct}</AccountNumber>"
            f"<ServiceNumber>{service_id}</ServiceNumber></SubscriberStatusRequest>")
    raw = request("POST", "/api/legacy/subscriber-status", body, timeout=config.LEGACY_TIMEOUT, xml=True, trace_id=trace_id, tool="legacy-subscriber-status")
    try:
        root = ET.fromstring(raw)
        fields = {k: root.findtext(k, "") for k in ("ACCT_NO", "SVC_NO", "SVC_STAT", "NET_STAT", "ERR_CD", "RESP_TS")}
    except ET.ParseError as e: raise ServiceFault("legacy_malformed", "Legacy response could not be parsed") from e
    if fields["ACCT_NO"] != acct or fields["SVC_NO"] != service_id: raise ServiceFault("legacy_mismatch", "Legacy response identity mismatch")
    code_map = {"0":"ok", "101":"account_missing", "102":"service_missing", "205":"auth_rejected", "301":"invalid_request", "429":"rate_limited", "503":"unavailable", "900":"unknown"}
    normalized = {"accountId": acct, "serviceId": service_id, "serviceStatus": fields["SVC_STAT"], "networkStatus": fields["NET_STAT"], "error": code_map.get(fields["ERR_CD"], "unknown"), "timestamp": fields["RESP_TS"]}
    if normalized["error"] != "ok": raise ServiceFault("legacy_" + normalized["error"], "Legacy service reported an error")
    emit("legacy.normalized", trace_id, component="legacy-adapter", metadata={"error": "ok"})
    return normalized


def create_case(account_id, customer_id, summary, key, trace_id):
    body = {"accountId":account_id, "customerId":customer_id, "summary":summary, "idempotencyKey":key}
    try:
        result = request("POST", "/api/support-cases", body, trace_id=trace_id, tool="case-management")
    except ServiceFault as e:
        if e.code not in {"503", "unavailable"}: raise
        emit("retry.performed", trace_id, component="case-management", status="pending", metadata={"attempt":2,"idempotent":True})
        result = request("POST", "/api/support-cases", body, trace_id=trace_id, tool="case-management")
    if not isinstance(result, dict) or not result.get("caseId") or result.get("status") != "open": raise ServiceFault("malformed", "Case response was not confirmed")
    return result
