"""Read-only inspection of the authorized home server's desktop runtime."""
import os
import paramiko

c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.123.47',username='roy',password=os.environ['GPU_PASS'],look_for_keys=False,allow_agent=False,timeout=20)
try:
    command="""printf 'User namespace sandbox\\n'; unshare -Ur true && echo NAMESPACE_OK
printf 'Desktop session\\n'; pgrep -a -u roy 'xfce4-panel|gnome-shell|plasmashell|Xorg|Xvnc' || true
printf 'Runtime libraries\\n'; ldconfig -p | awk '/libgtk-3.so|libnss3.so|libgbm.so|libasound.so|libXss.so|libappindicator|libayatana/ {print}'
printf 'Home Electron runtimes\\n'; find /home/roy/.local /home/roy/ultimate-video-tool-server -maxdepth 4 -type f -name electron 2>/dev/null
printf 'Session environment\\n'; systemctl --user show-environment | sed -n '/^DISPLAY=/p;/^XAUTHORITY=/p;/^DBUS_SESSION_BUS_ADDRESS=/p;/^XDG_CURRENT_DESKTOP=/p'
"""
    _,out,err=c.exec_command(command);print(out.read().decode());print(err.read().decode())
finally:c.close()
