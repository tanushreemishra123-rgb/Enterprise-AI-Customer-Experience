"""HTTP entry point for the productionized synthetic telecom CX workflow."""
import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote

from cx import config, security, engine
from cx.telemetry import metrics, recent_traces, trace, emit

UI = Path(__file__).with_name("ui")
COOKIE = "cx_session"


class Handler(BaseHTTPRequestHandler):
    def send_data(self, status, value, content_type="application/json", headers=None):
        body=value.encode() if isinstance(value,str) else json.dumps(value,ensure_ascii=False).encode()
        self.send_response(status); self.send_header("Content-Type",content_type+"; charset=utf-8")
        self.send_header("Content-Length",str(len(body))); self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff"); self.send_header("Referrer-Policy","no-referrer")
        for k,v in (headers or {}).items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(body)

    def get_sid(self):
        for part in self.headers.get("Cookie","").split(";"):
            k,_,v=part.strip().partition("=")
            if k==COOKIE: return v
        return ""

    def set_cookie(self, sid, clear=False):
        secure="; Secure" if __import__("os").getenv("COOKIE_SECURE","0")=="1" else ""
        age=0 if clear else config.SESSION_TTL_SECONDS
        return {"Set-Cookie":f"{COOKIE}={sid}; Path=/; HttpOnly; SameSite=Strict; Max-Age={age}{secure}"}

    def body(self):
        try: n=int(self.headers.get("Content-Length","0"))
        except ValueError: n=-1
        if n<0 or n>config.MAX_BODY_BYTES: raise ValueError("request body too large or invalid")
        raw=self.rfile.read(n) if n else b"{}"
        result=json.loads(raw)
        if not isinstance(result,dict): raise ValueError("JSON object required")
        return result

    def read_session(self, trace_id=None):
        sid=self.get_sid()
        state=security.session(sid,trace_id)
        return sid,state

    def do_GET(self):
        path=urlparse(self.path).path
        if path in {"/","/index.html"}:
            return self.serve("index.html","text/html")
        if path.startswith("/ui/"):
            name=path[4:]
            if name not in {"app.js","styles.css"}: return self.send_data(404,{"error":"not_found"})
            return self.serve(name,"application/javascript" if name.endswith("js") else "text/css")
        if path=="/health": return self.send_data(200,{"status":"ok","mode":config.AI_MODE})
        if path=="/mode":
            mode=config.AI_MODE
            if mode=="live" and not config.GEMINI_API_KEY: mode="degraded"
            sid,state=self.read_session()
            return self.send_data(200,{"mode":mode,"requested":config.AI_MODE,"liveCredentialConfigured":bool(config.GEMINI_API_KEY)})
        if path in {"/metrics","/traces","/escalations","/ops"}:
            sid,state=self.read_session()
            try: security.require_support(state,"TRACE-OPS")
            except security.ServiceFault as e: return self.send_data(403,{"error":e.code,"answer":str(e)})
            if path=="/metrics": return self.send_data(200,metrics())
            if path=="/traces": return self.send_data(200,{"traces":recent_traces()})
            if path=="/escalations":
                rows=self.load_escalations()
                return self.send_data(200,{"escalations":rows})
            return self.send_data(200,{"metrics":metrics(),"traces":recent_traces(),"escalations":self.load_escalations()})
        if path.startswith("/trace/"):
            sid,state=self.read_session()
            try: security.require_support(state,"TRACE-OPS")
            except security.ServiceFault as e: return self.send_data(403,{"error":e.code})
            tid=unquote(path.removeprefix("/trace/"))
            return self.send_data(200,{"traceId":tid,"events":trace(tid)})
        return self.send_data(404,{"error":"not_found"})

    def do_POST(self):
        path=urlparse(self.path).path
        trace_id="TRACE-"+secrets.token_hex(8)
        try: data=self.body()
        except (ValueError,json.JSONDecodeError) as e: return self.send_data(400,{"error":"invalid_request","answer":str(e)})
        if path=="/login":
            old_sid,old= self.read_session()
            try: sid,state=security.login(data.get("username",""),data.get("password",""),trace_id)
            except security.ServiceFault as e: return self.send_data(503 if e.code=="auth_unavailable" else 401,{"error":e.code,"answer":str(e)})
            if old and not old.get("customer_id"):
                for key in ("pending","turns","request","completed","verified"):
                    if key in old: state[key]=old[key]
            if old:
                security.logout(old_sid)
            return self.send_data(200,{"identity":{"customerId":state["customer_id"],"accountId":state["account_id"],"roles":state["roles"]}},headers=self.set_cookie(sid))
        if path=="/logout":
            sid=self.get_sid(); security.logout(sid)
            return self.send_data(200,{"ok":True},headers=self.set_cookie("",True))
        if path=="/chat":
            sid,state=self.read_session(trace_id)
            if state is None: sid,state=security.anonymous_session()
            try:
                state,result=engine.process(data.get("message",""),state,trace_id,sid)
                return self.send_data(200,result,headers=self.set_cookie(sid))
            except security.ServiceFault as e:
                emit("workflow.failed",trace_id,sid,"orchestrator","denied" if e.code in {"forbidden","unauthorized"} else "failure",metadata={"code":e.code})
                status=403 if e.code=="forbidden" else 401 if e.code=="unauthorized" else 400
                return self.send_data(status,{"error":e.code,"answer":str(e),"traceId":trace_id},headers=self.set_cookie(sid))
        return self.send_data(404,{"error":"not_found"})

    def serve(self,name,ctype):
        file=UI/name
        if not file.exists(): return self.send_data(404,{"error":"not_found"})
        return self.send_data(200,file.read_text(encoding="utf-8"),ctype,headers={"Content-Security-Policy":"default-src 'self'; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'"})

    @staticmethod
    def load_escalations():
        file=Path(__file__).resolve().parent/"escalations.jsonl"
        rows=[]
        if file.exists():
            for line in file.read_text(encoding="utf-8").splitlines()[-100:]:
                try: rows.append(json.loads(line))
                except ValueError: pass
        return rows

    def log_message(self,*args): pass


if __name__=="__main__":
    print(f"CX resolution service listening on http://{config.APP_HOST}:{config.APP_PORT} ({config.AI_MODE})")
    ThreadingHTTPServer((config.APP_HOST,config.APP_PORT),Handler).serve_forever()
