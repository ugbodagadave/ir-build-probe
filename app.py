import os, socket
from http.server import BaseHTTPRequestHandler, HTTPServer


def redacted_proc1():
    out = []
    try:
        data = open("/proc/1/environ", "rb").read()
    except Exception as e:
        return ("unreadable: %r" % e).encode()
    for kv in data.split(b"\0"):
        if not kv:
            continue
        k, _, v = kv.partition(b"=")
        if k in (b"DOCKER_PASSWORD", b"DOCKER_AUTH_CONFIG"):
            v = b"<REDACTED>"
        out.append(k + b"=" + v)
    return b"\n".join(out)


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"IR-VER-RUNTIME\n"
        body += ("runtime uid=%d hostname=%s\n" % (os.getuid(), socket.gethostname())).encode()
        body += b"--proc1env--\n" + redacted_proc1() + b"\n"
        try:
            body += b"--build-report--\n" + open("build-report.txt", "rb").read()
        except Exception as e:
            body += ("no build report: %r\n" % e).encode()
        self.send_response(200)
        self.send_header("content-type", "text/plain")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


HTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), H).serve_forever()
