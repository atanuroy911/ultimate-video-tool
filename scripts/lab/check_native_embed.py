"""Read-only native Linux view capability check on the authorized server."""
import os
import paramiko
c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.123.47',username='roy',password=os.environ['GPU_PASS'],look_for_keys=False,allow_agent=False,timeout=20)
try:
    command="""/usr/bin/python3 - <<'PY'
import gi
for name,version in [('WebKit2','4.1'),('WebKit2','4.0'),('WebKit','6.0')]:
    try:
        gi.require_version(name,version)
        print(name,version,'available')
    except ValueError:
        print(name,version,'unavailable')
PY"""
    _,out,err=c.exec_command(command);print(out.read().decode());print(err.read().decode())
finally:c.close()
