import setuptools, os, socket

print("VER-NOPROBE-BUILD-MARKER uid=%d host=%s" % (os.getuid(), socket.gethostname()))
setuptools.setup(name="ir-ver-noprobe", version="1.0.0", packages=[])
