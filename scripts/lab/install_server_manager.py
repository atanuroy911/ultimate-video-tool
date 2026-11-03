"""Add the shared native server manager to the existing authorized home install."""
import json
import os
from pathlib import Path
import paramiko

local=Path(__file__).resolve().parents[2]
root='/home/roy/ultimate-video-tool-server'
c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.123.47',username='roy',password=os.environ['GPU_PASS'],look_for_keys=False,allow_agent=False,timeout=20)
s=c.open_sftp()
try:
    _,out,err=c.exec_command(f'mkdir -p {root}/manager/app {root}/manager/runtime /home/roy/.local/share/applications /home/roy/.config/autostart')
    assert out.channel.recv_exit_status()==0,err.read().decode()
    for name in ['server-manager.js','server-manager-entry.js','server-manager-preload.js','server-manager.html','server-manager-ui.js','server-control.js','server-icon.png']:
        s.put(str(local/'server/desktop'/name),root+'/manager/app/'+name)
    s.put(str(local/'server/packaging/engine/server-manager-gtk.py'),root+'/manager/app/server-manager-gtk.py')
    desktop='/home/roy/.local/share/applications/ultimate-video-tool-server.desktop'
    config={'root':root,'url':'http://127.0.0.1:8790','service':'ultimate-video-tool.service','launcher':root+'/open-server-manager.sh','desktopFile':desktop}
    for file,value in [('server-manager-config.json',config),('package.json',{'name':'ultimate-video-tool-server','productName':'Ultimate Video Tool Server','version':'1.0.0','main':'server-manager-entry.js'})]:
        with s.file(root+'/manager/app/'+file,'w') as f:f.write(json.dumps(value,indent=2))
    launcher=f'''#!/bin/sh
set -eu
# A native GTK window handles desktops that restrict browser namespaces.
if unshare -Ur true 2>/dev/null; then
  exec "{root}/manager/runtime/node_modules/electron/dist/electron" --disable-setuid-sandbox "{root}/manager/app" "$@"
fi
exec /usr/bin/python3 "{root}/manager/app/server-manager-gtk.py" "$@"
'''
    with s.file(root+'/open-server-manager.sh','w') as f:f.write(launcher)
    s.chmod(root+'/open-server-manager.sh',0o700)
    entry=f'''[Desktop Entry]
Version=1.0
Type=Application
Name=Ultimate Video Tool Server
Comment=Manage your video server and connect client computers
Exec="{root}/open-server-manager.sh"
Icon={root}/manager/app/server-icon.png
Terminal=false
Categories=AudioVideo;Network;
StartupNotify=true
StartupWMClass=ultimate-video-tool-server
'''
    with s.file(desktop,'w') as f:f.write(entry)
    s.chmod(desktop,0o755)
    with s.file('/home/roy/.config/autostart/ultimate-video-tool-server.desktop','w') as f:f.write(entry.replace('open-server-manager.sh"','open-server-manager.sh" --background'))
    install=f'''#!/bin/bash
set -euo pipefail
export PATH="{root}/node/bin:/usr/bin:/bin" ELECTRON_CACHE="{root}/cache/electron"
cd "{root}/manager/runtime"
if unshare -Ur true 2>/dev/null; then
if [ ! -x node_modules/electron/dist/electron ]; then
  npm install --no-audit --no-fund --cache "{root}/cache/npm" --save-exact electron@33.4.11
fi
else
  /usr/bin/python3 -c "import gi; gi.require_version('Gtk','3.0')"
fi
update-desktop-database /home/roy/.local/share/applications || true
DESKTOP=$(xdg-user-dir DESKTOP)
if [[ "$DESKTOP" == /home/roy/* && -d "$DESKTOP" ]]; then
  cp "{desktop}" "$DESKTOP/Ultimate Video Tool Server.desktop"
  chmod 755 "$DESKTOP/Ultimate Video Tool Server.desktop"
fi
export DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
pkill -u roy -f '^/usr/bin/python3 {root}/manager/app/server-manager-gtk.py$' || true
nohup "{root}/open-server-manager.sh" --engines > "{root}/manager.log" 2>&1 < /dev/null &
echo MANAGER_READY
'''
    with s.file(root+'/install-manager.sh','w') as f:f.write(install)
    s.chmod(root+'/install-manager.sh',0o700)
    _,out,err=c.exec_command(f'nohup {root}/install-manager.sh > {root}/manager-install.log 2>&1 < /dev/null & echo $!')
    print('Server manager installation started:',out.read().decode().strip());print(err.read().decode())
finally:s.close();c.close()
