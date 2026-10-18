"""Run SCN-001..008 through the app engine against supplied local mock services."""
import json, os, subprocess, sys, time, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("AI_MODE","reviewer")
from cx import security, engine, config

MOCK=ROOT/"mock-services"/"server.py"

class Mock:
    def __init__(self,**extra): self.extra=extra;self.proc=None
    def __enter__(self):
        env=dict(os.environ);env.update(self.extra);env["MOCK_PORT"]="8090"
        self.proc=subprocess.Popen([sys.executable,str(MOCK)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(60):
            try:
                with urllib.request.urlopen("http://localhost:8090/health",timeout=.25): return self
            except Exception: time.sleep(.1)
        raise RuntimeError("mock-services did not become healthy")
    def __exit__(self,*_):
        self.proc.terminate();self.proc.wait(timeout=5)

def login(customer="CUST-1001"):
    data=json.loads((ROOT/"sample-data"/"customers.json").read_text())
    user=next(x for x in data["customers"] if x["customerId"]==customer)
    return security.login(user["username"],user["testPassword"],"TRACE-login")[1]

def ask(state,text,trace): return engine.process(text,state,trace,state.get("session_id","eval"))[1]

def main():
    results=[]
    config.AI_MODE="reviewer"
    with Mock():
        s=login();r=ask(s,"What internet plan am I currently using?","SCN-001");results.append(("SCN-001", "Fiber 500" in r["answer"] and r.get("evidence",{}).get("source")=="account-service"))
        s=login();_,r=engine.process("My service is not working.",s,"SCN-002-A",s["session_id"]);_,r=engine.process("home internet",s,"SCN-002-B",s["session_id"]);results.append(("SCN-002", "home internet or mobile" in r["answer"].lower() or bool(r.get("evidence"))))
        s=login();r=ask(s,"My home internet has been unavailable since this morning.","SCN-003");results.append(("SCN-003",bool(r.get("evidence") or r.get("escalation"))))
        s=login();_,proposal=engine.process("Create a support case for my internet issue",s,"SCN-004-A",s["session_id"]);_,done=engine.process("CONFIRM",s,"SCN-004-B",s["session_id"]);results.append(("SCN-004",proposal.get("confirmationRequired") is True and bool(done.get("caseId"))))
        s=login();
        try: ask(s,"What plan is on ACC-2002?","SCN-005");denied=False
        except security.ServiceFault as e: denied=e.code=="forbidden"
        results.append(("SCN-005",denied))
        s=login();r=ask(s,"Show my subscriber status","SCN-006");results.append(("SCN-006",bool(r.get("evidence",{}).get("sources")) and "<" not in r["answer"]))
    with Mock(MOCK_CASE_MODE="unavailable"):
        s=login();_,p=engine.process("Create a support case for my internet issue",s,"SCN-007-A",s["session_id"]);_,r=engine.process("CONFIRM",s,"SCN-007-B",s["session_id"]);results.append(("SCN-007",bool(r.get("escalation")) and "not report" in r["answer"].lower()))
    config.AI_MODE="live";os.environ["MOCK_GEMINI_MODE"]="unavailable"
    with Mock():
        s=login();r=ask(s,"What internet plan am I currently using?","SCN-008");results.append(("SCN-008",r.get("mode")=="degraded" and "Fiber 500" in r["answer"]))
    output=[{"scenario":k,"passed":v} for k,v in results]
    dest=Path(__file__).with_name("scenario-results.json");dest.write_text(json.dumps(output,indent=2)+"\n",encoding="utf-8")
    for item in output: print(f"{item['scenario']}: {'PASS' if item['passed'] else 'FAIL'}")
    print(f"{sum(v for _,v in results)}/{len(results)} scenarios passed")
    return 0 if all(v for _,v in results) else 1

if __name__=="__main__": raise SystemExit(main())
