import os
from http.server import BaseHTTPRequestHandler, HTTPServer
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"IR-PYPACK-RUNTIME\n"
        try:
            body += open("build-report.txt","rb").read()
        except Exception as e:
            body += ("no report: %r"%e).encode()
        self.send_response(200); self.send_header("content-type","text/plain"); self.end_headers(); self.wfile.write(body)
    def log_message(self,*a): pass
HTTPServer(("0.0.0.0", int(os.environ.get("PORT","8080"))), H).serve_forever()
