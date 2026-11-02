"""Upload one local file to the GPU server: put.py <local> <remote>  (password from GPU_PASS)."""
import os
import sys

import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.123.47", username="roy", password=os.environ["GPU_PASS"], timeout=15, look_for_keys=False, allow_agent=False)
sftp = c.open_sftp()
sftp.put(sys.argv[1], sys.argv[2])
print("uploaded", os.path.getsize(sys.argv[1]), "bytes to", sys.argv[2])
c.close()
