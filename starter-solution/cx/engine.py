"""Deterministic workflows around constrained Gemini interpretation."""
import hashlib
import time
import uuid

from . import config, enterprise
from .ai import classify, reviewer_intent
from .security import ServiceFault, authorize
from .telemetry import emit, redact


def _escalate(trace_id, session_id, state, reason, systems, next_step):
    record={"escalationId":"ESC-"+uuid.uuid4().hex[:10].upper(), "traceId":trace_id,
            "customerId":state.get("customer_id") if state else None,
            "requestSummary":redact((state or {}).get("request", ""))[:240],
            "completedSteps":(state or {}).get("completed", []), "systemsAccessed":systems,
            "verifiedContext":(state or {}).get("verified", {}), "failedIntegrations":[reason],
            "reason":reason,"pendingAction":"Support should review before retrying or completing an action.",
            "recommendedNextStep":next_step}
    if not record["customerId"]: record.pop("customerId")
    from pathlib import Path
    path=Path(__file__).resolve().parents[2]/"starter-solution"/"escalations.jsonl"
    with path.open("a",encoding="utf-8") as f: f.write(__import__("json").dumps(record)+"\n")
    emit("escalation.created",trace_id,session_id,"case-management",metadata={"reason":reason})
    state["status"]="escalated"
    return record


def _result(answer, trace_id, session_id, mode, **extra):
    # Session credentials stay in the HttpOnly cookie and server-side session store.
    return {"answer":answer,"traceId":trace_id,"mode":mode,**extra}


def _issue(message, intent, user_state, trace_id, session_id, mode, account_id):
    completed=[]; systems=[]; verified={}
    try:
        profile=enterprise.customer(user_state["customer_id"],trace_id); systems.append("customer-profile");completed.append("customer profile retrieved")
        account=enterprise.account(account_id,trace_id); systems.append("account-service");completed.append("account retrieved")
        if account.get("customerId") != user_state["customer_id"] and "support-agent" not in user_state.get("roles", []):
            raise ServiceFault("forbidden","Account ownership mismatch")
        if not profile.get("postalCode"): raise ServiceFault("incomplete","Postal code missing from profile")
        outage=enterprise.outage(str(profile["postalCode"]),trace_id);systems.append("network-outage");completed.append("network status checked")
        legacy=enterprise.legacy(account,trace_id);systems.append("legacy-subscriber-status");completed.append("subscriber status normalized")
        verified={"networkStatus":outage.get("status"),"subscriberStatus":legacy.get("serviceStatus"),"lineStatus":legacy.get("networkStatus")}
        answer=(f"The area network service reports {outage['status']}. The subscriber system reports "
                f"service status {legacy['serviceStatus']} and network status {legacy['networkStatus']}. "
                "Sources: network outage service and normalized legacy subscriber service.")
        user_state["completed"]=completed;user_state["verified"]=verified;user_state["status"]="resolved"
        emit("workflow.resolved",trace_id,session_id,metadata={"intent":intent})
        return _result(answer,trace_id,session_id,mode,evidence={"sources":systems,"verified":verified})
    except ServiceFault as e:
        user_state["completed"]=completed;user_state["verified"]=verified
        record=_escalate(trace_id,session_id,user_state,e.code,systems,"Review the failed integration and continue diagnostics.")
        emit("workflow.escalated",trace_id,session_id,"orchestrator",status="failure",metadata={"code":e.code})
        return _result("I could not verify the service status, so I have not claimed a resolution. Support will continue with the recorded checks.",trace_id,session_id,mode,escalation=record)


def process(message, state, trace_id, session_id):
    """Run a single user turn and preserve pending workflow state in the session."""
    message=str(message or "").strip()
    if not message or len(message)>2000: raise ServiceFault("invalid_request","Enter a request of 1–2,000 characters")
    emit("request.received",trace_id,session_id,metadata={"messageLength":len(message)})
    if state is None: state={"pending":None,"roles":[]}
    state["turns"]=state.get("turns",0)+1
    if state["turns"]>config.MAX_TURNS: state["pending"]=None;state["turns"]=0
    pending=state.get("pending")
    mode=config.AI_MODE if config.AI_MODE in {"reviewer","live"} else "reviewer"
    if pending and pending.get("kind")=="confirmation":
        if message.lower() not in {"yes","confirm","confirmed","yes, create it","go ahead"}:
            state["pending"]=None;emit("confirmation.declined",trace_id,session_id,status="denied")
            return state,_result("Okay, I have not created a case.",trace_id,session_id,mode)
        authorize(state,pending["account_id"],trace_id)
        emit("confirmation.received",trace_id,session_id,component="case-management")
        try:
            case=enterprise.create_case(pending["account_id"],state.get("customer_id",""),pending["summary"],pending["idempotency_key"],trace_id)
            state["pending"]=None;state["status"]="resolved"
            emit("action.completed",trace_id,session_id,"case-management",metadata={"caseId":case["caseId"],"duplicate":bool(case.get("duplicate"))})
            emit("workflow.resolved",trace_id,session_id)
            msg=(f"Support case {case['caseId']} was created and verified." if not case.get("duplicate") else f"A matching case already exists: {case['caseId']}. No duplicate was created.")
            return state,_result(msg,trace_id,session_id,mode,caseId=case["caseId"],duplicate=bool(case.get("duplicate")))
        except ServiceFault as e:
            state["pending"]=None
            rec=_escalate(trace_id,session_id,state,e.code,["case-management"],"Check whether the case exists before resubmission.")
            return state,_result("The case service did not confirm creation. I have not reported it as successful; support will review it.",trace_id,session_id,mode,escalation=rec)
    if pending and pending.get("kind")=="clarification":
        follow=reviewer_intent(message)
        if follow["service"]=="unknown":
            return state,_result("Please specify home internet or mobile service.",trace_id,session_id,mode,clarificationRequired=True)
        message=pending["request"]+" " + message
        state["pending"]=None
    intent,mode=classify(message,trace_id,session_id)
    emit("intent.classified",trace_id,session_id,component="orchestrator",metadata={"intent":intent["intent"],"mode":mode})
    if intent["intent"]=="other":
        return state,_result("I can help with your plan, bill, service status or issue, and a support case. What would you like to do?",trace_id,session_id,mode)
    if intent["intent"]=="service_issue" and intent["service"]=="unknown":
        state["pending"]={"kind":"clarification","request":message}
        emit("clarification.requested",trace_id,session_id,status="pending",metadata={"field":"service"})
        return state,_result("Which service is affected: home internet or mobile? I’ll keep your issue details and continue after you clarify.",trace_id,session_id,mode,clarificationRequired=True)
    account_id=intent["account_id"] or (state or {}).get("account_id")
    protected=intent["intent"]!="other"
    if protected and not state.get("customer_id"):
        emit("authentication.required",trace_id,session_id,status="denied")
        return state,_result("Please sign in before I access protected account or service information.",trace_id,session_id,mode,needsAuthentication=True)
    account_id=account_id or state.get("account_id")
    if not account_id:
        return state,_result("I could not identify your account. Please sign in or clarify the account reference.",trace_id,session_id,mode,needsAuthentication=True)
    authorize(state,account_id,trace_id)
    try:
        acc=enterprise.account(account_id,trace_id)
        if acc.get("customerId")!=state.get("customer_id") and "support-agent" not in state.get("roles",[]):
            raise ServiceFault("forbidden","Account ownership validation failed")
    except ServiceFault as e:
        if e.code=="forbidden": raise
        rec=_escalate(trace_id,session_id,{**state,"request":message,"completed":[]},e.code,["account-service"],"Verify account-service availability and retry.")
        return state,_result("I could not retrieve the account information; support will investigate.",trace_id,session_id,mode,escalation=rec)
    if intent["intent"]=="plan":
        plan=acc.get("plan",{});name=plan.get("name")
        if not name: raise ServiceFault("incomplete","Plan information is missing")
        emit("workflow.resolved",trace_id,session_id)
        return state,_result(f"Your account lists the {name} plan. Source: account service ({account_id}).",trace_id,session_id,mode,evidence={"source":"account-service","accountId":account_id,"plan":plan})
    if intent["intent"]=="billing":
        try: bill=enterprise.billing(account_id,trace_id)
        except ServiceFault as e:
            rec=_escalate(trace_id,session_id,{**state,"request":message},e.code,["account-service","billing-service"],"Verify billing service availability before replying.")
            return state,_result("I could not verify the bill, so I will not guess at the amount. Support will review it.",trace_id,session_id,mode,escalation=rec)
        emit("workflow.resolved",trace_id,session_id)
        return state,_result(f"Your bill for {bill['period']} totals ${bill['total']:.2f}. Source: billing service ({account_id}).",trace_id,session_id,mode,evidence={"source":"billing-service","accountId":account_id,"period":bill["period"],"total":bill["total"]})
    if intent["intent"] in {"service_issue","service_status"}:
        state.update({"request":message,"account_id":account_id})
        return state,_issue(message,intent["intent"],state,trace_id,session_id,mode,account_id)
    if intent["intent"]=="create_case":
        summary=redact(message)[:240]
        bucket=int(time.time()//600)
        idem="case-"+hashlib.sha256(f"{state['customer_id']}|{account_id}|{summary.lower()}|{bucket}".encode()).hexdigest()[:24]
        state["pending"]={"kind":"confirmation","account_id":account_id,"summary":summary,"idempotency_key":idem}
        emit("confirmation.requested",trace_id,session_id,"case-management",status="pending")
        return state,_result(f"I can create a support case for account {account_id}: {summary}. Reply CONFIRM to submit it, or CANCEL to stop.",trace_id,session_id,mode,confirmationRequired=True)
    return state,_result("I could not safely route that request.",trace_id,session_id,mode)
