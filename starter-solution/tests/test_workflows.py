import unittest
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cx import ai, engine, security
from cx.enterprise import ServiceFault
from cx import enterprise
from cx.telemetry import redact, reset, trace, emit, metrics


class InterpretationTests(unittest.TestCase):
    def test_reviewer_routes_supported_requests(self):
        self.assertEqual(ai.reviewer_intent("What internet plan do I have?")["intent"],"plan")
        self.assertEqual(ai.reviewer_intent("my bill is too high")["intent"],"billing")
        self.assertEqual(ai.reviewer_intent("create a support case for my mobile issue")["intent"],"create_case")

    def test_account_ref_is_extracted_but_not_authorized(self):
        self.assertEqual(ai.reviewer_intent("Plan for ACC-2002?")["account_id"],"ACC-2002")

    def test_model_output_is_enum_and_type_checked(self):
        self.assertEqual(ai._validate({"intent":"plan","service":"unknown","account_id":"ACC-2001","summary":"ok"})["account_id"],"ACC-2001")
        with self.assertRaises(ValueError): ai._validate({"intent":"execute-transfer","service":"unknown"})

    def test_model_input_redacts_secrets_and_pii(self):
        value=redact("my password=SuperSecret and mail a@b.com call 555-222-1234")
        self.assertNotIn("SuperSecret",value);self.assertNotIn("a@b.com",value);self.assertNotIn("555-222-1234",value)

    def test_provider_failure_enters_degraded_mode_without_network(self):
        with patch("cx.ai.config.AI_MODE","live"),patch("cx.ai.config.GEMINI_API_KEY",""):
            result,mode=ai.classify("What internet plan do I have?","TF","S")
        self.assertEqual(mode,"degraded");self.assertEqual(result["intent"],"plan")


class AuthorizationTests(unittest.TestCase):
    def setUp(self): self.customer={"customer_id":"CUST-1001","account_id":"ACC-2001","roles":["customer"],"session_id":"s"}

    def test_customer_can_access_own_account(self): self.assertTrue(security.authorize(self.customer,"ACC-2001","T"))

    def test_cross_customer_access_is_denied(self):
        with self.assertRaises(ServiceFault) as e: security.authorize(self.customer,"ACC-2002","T")
        self.assertEqual(e.exception.code,"forbidden")

    def test_unauthenticated_protected_access_is_denied(self):
        with self.assertRaises(ServiceFault): security.authorize(None,"ACC-2001","T")

    def test_support_agent_can_access_customer_accounts(self):
        agent={"customer_id":"AGENT-3001","roles":["support-agent"]}
        self.assertTrue(security.authorize(agent,"ACC-2002","T"))

    def test_ops_are_support_agent_only(self):
        with self.assertRaises(ServiceFault): security.require_support(self.customer,"T")
        security.require_support({"roles":["support-agent"]},"T")

    def test_auth_success_keeps_bearer_token_out_of_session(self):
        payload={"accessToken":"synthetic-bearer","customerId":"CUST-1001","accountId":"ACC-2001","roles":["customer"],"expiresIn":3600}
        with patch("cx.security._call_auth",return_value=(200,payload)):
            sid,state=security.login("alex.morgan","dummy","TA")
        self.assertTrue(security.session(sid));self.assertNotIn("token",state);self.assertNotIn("accessToken",state)

    def test_invalid_or_expired_auth_is_rejected(self):
        with patch("cx.security._call_auth",return_value=(401,{})):
            with self.assertRaises(ServiceFault): security.login("alex.morgan","wrong","TB")
        expired={"accessToken":"expired","customerId":"CUST-1001","expiresIn":0}
        with patch("cx.security._call_auth",return_value=(200,expired)):
            with self.assertRaises(ServiceFault): security.login("alex.morgan","dummy","TC")

    def test_expired_server_session_is_removed(self):
        payload={"accessToken":"token","customerId":"CUST-1001","accountId":"ACC-2001","roles":["customer"],"expiresIn":3600}
        with patch("cx.security._call_auth",return_value=(200,payload)): sid,state=security.login("u","p","TD")
        state["expires_at"]=0
        self.assertIsNone(security.session(sid,"TE"))


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        reset();self.state={"session_id":"S","customer_id":"CUST-1001","account_id":"ACC-2001","roles":["customer"],"pending":None}
        self.account={"accountId":"ACC-2001","customerId":"CUST-1001","plan":{"name":"Fiber 500"},"services":[{"serviceId":"SVC-5001","type":"home-internet","status":"active"}]}

    def test_grounded_plan_uses_enterprise_value(self):
        with patch("cx.enterprise.account",return_value=self.account):
            _,result=engine.process("What internet plan am I currently using?",self.state,"T","raw-cookie-session-id")
        self.assertIn("Fiber 500",result["answer"]);self.assertEqual(result["evidence"]["source"],"account-service")
        self.assertNotIn("sessionId",result)
        self.assertNotIn("raw-cookie-session-id",str(result))

    def test_clarification_resumes_saved_issue(self):
        _,first=engine.process("My service is not working",self.state,"T1","S")
        self.assertTrue(first["clarificationRequired"])
        with patch("cx.enterprise.account",return_value=self.account),patch("cx.enterprise.customer",return_value={"customerId":"CUST-1001","postalCode":"94105"}),patch("cx.enterprise.outage",return_value={"postalCode":"94105","status":"normal"}),patch("cx.enterprise.legacy",return_value={"serviceStatus":"A","networkStatus":"DEGRADED"}):
            _,second=engine.process("home internet",self.state,"T2","S")
        self.assertTrue(second.get("evidence"));self.assertFalse(second.get("clarificationRequired",False))

    def test_case_action_waits_for_confirmation(self):
        with patch("cx.enterprise.account",return_value=self.account):
            _,proposal=engine.process("Create a support case for my internet issue",self.state,"T1","S")
        self.assertTrue(proposal["confirmationRequired"])
        with patch("cx.enterprise.create_case",return_value={"caseId":"CASE-123","status":"open"}):
            _,done=engine.process("CONFIRM",self.state,"T2","S")
        self.assertEqual(done["caseId"],"CASE-123")

    def test_case_cancel_does_not_execute(self):
        self.state["pending"]={"kind":"confirmation","account_id":"ACC-2001","summary":"issue","idempotency_key":"id"}
        with patch("cx.enterprise.create_case") as create:
            _,result=engine.process("cancel",self.state,"T","S")
        create.assert_not_called();self.assertNotIn("caseId",result)

    def test_confirmation_service_failure_escalates_without_success(self):
        self.state["pending"]={"kind":"confirmation","account_id":"ACC-2001","summary":"issue","idempotency_key":"id"}
        with patch("cx.enterprise.create_case",side_effect=ServiceFault("503")):
            _,result=engine.process("confirm",self.state,"T","S")
        self.assertTrue(result.get("escalation"));self.assertNotIn("created",result["answer"].lower())

    def test_billing_is_validated_and_grounded(self):
        bill={"accountId":"ACC-2001","period":"2026-09","total":84.99}
        with patch("cx.enterprise.account",return_value=self.account),patch("cx.enterprise.billing",return_value=bill):
            _,result=engine.process("What is my bill?",self.state,"TB","S")
        self.assertIn("$84.99",result["answer"]);self.assertEqual(result["evidence"]["source"],"billing-service")

    def test_legacy_xml_is_normalized_and_identity_checked(self):
        acct={"accountId":"ACC-2001","services":[{"serviceId":"SVC-5001"}]}
        xml="<R><ACCT_NO>ACC-2001</ACCT_NO><SVC_NO>SVC-5001</SVC_NO><SVC_STAT>A</SVC_STAT><NET_STAT>DEGRADED</NET_STAT><ERR_CD>0</ERR_CD><RESP_TS>now</RESP_TS></R>"
        with patch("cx.enterprise.request",return_value=xml):
            normalized=enterprise.legacy(acct,"TL")
        self.assertEqual(normalized["networkStatus"],"DEGRADED");self.assertNotIn("<",str(normalized))
        with patch("cx.enterprise.request",return_value=xml.replace("ACC-2001","ACC-9999")):
            with self.assertRaises(ServiceFault): enterprise.legacy(acct,"TL2")

    def test_malformed_billing_response_fails_closed(self):
        with patch("cx.enterprise.request",return_value={"unexpected":True}):
            with self.assertRaises(ServiceFault): enterprise.billing("ACC-2001","TM")

    def test_idempotent_case_retry_returns_existing_reference(self):
        with patch("cx.enterprise.request",return_value={"caseId":"CASE-77","status":"open","duplicate":True}):
            result=enterprise.create_case("ACC-2001","CUST-1001","issue","idem","TC")
        self.assertEqual(result["caseId"],"CASE-77");self.assertTrue(result["duplicate"])

    def test_workflow_trace_has_correlated_events(self):
        with patch("cx.enterprise.account",return_value=self.account):
            engine.process("What internet plan am I currently using?",self.state,"TRACE-CORR","S")
        names=[e["eventType"] for e in trace("TRACE-CORR")]
        self.assertIn("request.received",names);self.assertIn("workflow.resolved",names)


class TelemetryTests(unittest.TestCase):
    def setUp(self): reset()
    def test_sensitive_event_metadata_is_redacted(self):
        emit("auth.attempted","T","S",metadata={"password":"DUMMY_SECRET"})
        self.assertNotIn("DUMMY_SECRET",str(trace("T")))
    def test_session_ids_are_hashed_and_correlatable(self):
        raw_session_id="raw-cookie-session-id"
        emit("request.received","T",raw_session_id)
        emit("workflow.resolved","T",raw_session_id)
        events=trace("T")
        references={event["sessionId"] for event in events}
        self.assertEqual(len(references),1)
        self.assertTrue(next(iter(references)).startswith("sess-"))
        self.assertNotIn(raw_session_id,str(events))
    def test_metrics_are_derived_from_real_events(self):
        self.assertEqual(metrics()["totalRequests"],0)
        emit("request.received","T","S");emit("workflow.resolved","T","S")
        emit("gemini.completed","T","S","gemini",duration_ms=25)
        emit("tool.failed","T","S","billing","failure",metadata={"tool":"billing"})
        self.assertEqual(metrics()["totalRequests"],1);self.assertEqual(metrics()["resolved"],1)
        self.assertEqual(metrics()["averageGeminiLatencyMs"],25)
        self.assertEqual(metrics()["failuresByIntegration"],{"billing":1})


if __name__=="__main__": unittest.main()
