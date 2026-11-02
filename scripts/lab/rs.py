"""Run one shell command on the GPU server: rs.py "<command>"  (password from GPU_PASS)."""
import os
import sys

import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.123.47", username="roy", password=os.environ["GPU_PASS"], timeout=15, look_for_keys=False, allow_agent=False)
_, out, err = c.exec_command(sys.argv[1], get_pty=False, timeout=float(os.environ.get("RS_TIMEOUT", "600")))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
for line in out:
    print(line, end="")
e = err.read().decode("utf-8", "replace")
if e:
    print("[stderr] " + e[-3000:], end="")
code = out.channel.recv_exit_status()
c.close()
sys.exit(code)
