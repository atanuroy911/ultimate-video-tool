#!/usr/bin/python3
"""Native GTK fallback for desktop Linux hosts that restrict browser namespaces.

Uses the same local-only server API and home service as the Electron manager.
No web renderer, elevated helper, or operating-system policy change is needed.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import urllib.request
from urllib.parse import urlparse

import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk, Gio, GLib, Gdk

CONFIG=Path(__file__).with_name('server-manager-config.json')
config=json.loads(CONFIG.read_text())
root=Path(config['root']).resolve()
if not root.is_relative_to(Path.home().resolve()):raise RuntimeError('Server data must be in your home folder.')
base=config['url'].rstrip('/')
parsed=urlparse(base)
if parsed.hostname not in ('127.0.0.1','localhost','::1') or parsed.scheme not in ('http','https') or parsed.username or parsed.path not in ('',''):
    raise RuntimeError('Only a local processing server can be managed here.')
if config['service']!='ultimate-video-tool.service':raise RuntimeError('Unsupported processing service.')

def request(route,post=False):
    req=urllib.request.Request(base+route,data=b'{}' if post else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=6) as response:return json.load(response)

def service(action):
    result=subprocess.run(['systemctl','--user',action,config['service']],capture_output=True,text=True,timeout=30)
    if result.returncode:raise RuntimeError(result.stderr.strip() or 'The server action could not finish.')

class Manager(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.ultimatevideotool.ServerManager',flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window=None;self.tray=None;self.running=False;self.pending=False;self.checking=False;self.addresses=[];self.background=False
    def do_command_line(self,command):
        self.background='--background' in command.get_arguments();self.activate()
        if '--engines' in command.get_arguments():self.engine_settings()
        return 0
    def label(self,text='',large=False):
        item=Gtk.Label(label=text,xalign=0);item.set_line_wrap(True);item.set_selectable(True)
        if large:item.get_style_context().add_class('heading')
        return item
    def button(self,text,callback,primary=False):
        button=Gtk.Button(label=text);button.connect('clicked',lambda *_:callback())
        if primary:button.get_style_context().add_class('suggested-action')
        return button
    def card(self,parent,title):
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);box.set_border_width(22);box.get_style_context().add_class('card')
        box.pack_start(self.label(title,True),False,False,0);parent.pack_start(box,False,False,0);return box
    def do_activate(self):
        if self.window:
            if not self.background:self.window.show_all();self.window.present()
            return
        css=Gtk.CssProvider();css.load_from_data(b'window {background:#f4f5f8;color:#172239} .card {background:white;border-radius:16px;border:1px solid #e2e6ed} .heading {font-size:20px;font-weight:bold} .title {font-size:26px;font-weight:bold} button {padding:9px 14px;border-radius:9px} .suggested-action {background:#2563eb;color:white} .code {font: bold 29px monospace;color:#2563eb} .muted {color:#606b80}')
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.window=Gtk.ApplicationWindow(application=self,title='Ultimate Video Tool Server');self.window.set_default_size(720,820)
        self.window.set_icon_from_file(str(CONFIG.with_name('server-icon.png')));self.window.connect('delete-event',self.close)
        scroll=Gtk.ScrolledWindow();scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);self.window.add(scroll)
        self.stack=Gtk.Stack();scroll.add(self.stack)
        outer=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=16);outer.set_border_width(26);self.stack.add_named(outer,'overview')
        title=self.label('Ultimate Video Tool Server');title.get_style_context().add_class('title');outer.pack_start(title,False,False,0)
        outer.pack_start(self.label(os.uname().nodename),False,False,0)
        status=self.card(outer,'Your server');self.status=self.label('Checking…',True);status.pack_start(self.status,False,False,0)
        self.message=self.label('');status.pack_start(self.message,False,False,0)
        row=Gtk.Box(spacing=8);status.pack_start(row,False,False,0)
        self.workspace=self.button('Engine settings',self.engine_settings,True);row.pack_start(self.workspace,False,False,0)
        self.toggle=self.button('Start server',lambda:self.change('stop' if self.running else 'start'));row.pack_start(self.toggle,False,False,0)
        self.restart=self.button('Restart',lambda:self.change('restart'));row.pack_start(self.restart,False,False,0)
        pair=self.card(outer,'Connect a client');pair.pack_start(self.label('Open Ultimate Video Tool on your other PC. Choose this server, then enter its one-use connection code.'),False,False,0)
        self.address=self.label('');pair.pack_start(self.address,False,False,0)
        row=Gtk.Box(spacing=8);pair.pack_start(row,False,False,0)
        self.connect_button=self.button('Get connection code',self.code,True);row.pack_start(self.connect_button,False,False,0)
        self.copy_button=self.button('Copy address',self.copy);row.pack_start(self.copy_button,False,False,0)
        self.code_label=self.label('');self.code_label.get_style_context().add_class('code');pair.pack_start(self.code_label,False,False,0)
        pair.pack_start(self.label('A code works once. Creating another code replaces the previous one; approved clients stay connected.'),False,False,0)
        settings=self.card(outer,'Programs and models');settings.pack_start(self.label('Open server settings to connect ComfyUI and Ollama or choose installation and model folders. Stopping this server leaves your existing engines running.'),False,False,0)
        self.auto=Gtk.CheckButton(label='Start when I sign in');self.auto.set_active(Path.home().joinpath('.config/autostart/ultimate-video-tool-server.desktop').exists());self.auto.connect('toggled',self.auto_changed);settings.pack_start(self.auto,False,False,0)
        settings.pack_start(self.label('Close this window to keep the server in the tray.'),False,False,0)
        row=Gtk.Box(spacing=8);outer.pack_start(row,False,False,0)
        row.pack_start(self.button('View log',self.show_log),False,False,0)
        row.pack_start(self.button('Refresh status',self.refresh),False,False,0)
        row.pack_start(self.button('Quit server',lambda:self.change('quit')),False,False,0)
        self.make_tray();self.window.show_all()
        if self.background and self.tray:self.window.hide()
        self.refresh();GLib.timeout_add_seconds(5,self.refresh)
    def make_tray(self):
        menu=Gtk.Menu();self.tray_items={}
        for title,fn in [('Open server manager',self.show),('Engine settings',self.engine_settings),('Connect a client',self.code),('Start server',lambda:self.change('start')),('Stop server',lambda:self.change('stop')),('Quit server',lambda:self.change('quit'))]:
            item=Gtk.MenuItem(label=title);item.connect('activate',lambda _,fn=fn:fn());menu.append(item);self.tray_items[title]=item
        menu.show_all()
        try:
            gi.require_version('AyatanaAppIndicator3','0.1');from gi.repository import AyatanaAppIndicator3 as Indicator
            self.tray=Indicator.Indicator.new('ultimate-video-tool-server',str(CONFIG.with_name('server-icon.png')),Indicator.IndicatorCategory.APPLICATION_STATUS);self.tray.set_status(Indicator.IndicatorStatus.ACTIVE);self.tray.set_menu(menu)
        except (ValueError,ImportError):
            self.tray=Gtk.StatusIcon.new_from_file(str(CONFIG.with_name('server-icon.png')));self.tray.set_tooltip_text('Ultimate Video Tool Server');self.tray.connect('activate',lambda *_:self.show());self.tray.connect('popup-menu',lambda icon,button,time:menu.popup(None,None,Gtk.StatusIcon.position_menu,icon,button,time))
    def show(self):self.window.show_all();self.window.present()
    def close(self,*_):
        if self.tray:self.window.hide();return True
        self.quit();return False
    def overview(self):self.stack.set_visible_child_name('overview');self.show()
    def engine_settings(self):
        if not self.stack.get_child_by_name('engines'):
            try:
                try:gi.require_version('WebKit2','4.1')
                except ValueError:gi.require_version('WebKit2','4.0')
                from gi.repository import WebKit2
            except (ValueError,ImportError):
                self.message.set_text('The native embedded settings component is unavailable. The server stays running.');self.overview();return
            panel=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);panel.set_border_width(12)
            panel.pack_start(self.button('← Server overview',self.overview),False,False,0)
            self.engine_browser=WebKit2.WebView();self.engine_browser.set_size_request(-1,650)
            def navigation(view,decision,kind):
                if kind in (WebKit2.PolicyDecisionType.NAVIGATION_ACTION,WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION):
                    uri=decision.get_navigation_action().get_request().get_uri()
                    if kind==WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION or not uri.startswith(base+'/'):
                        decision.ignore();return True
                return False
            self.engine_browser.connect('decide-policy',navigation)
            self.engine_browser.connect('create',lambda *_:None)
            panel.pack_start(self.engine_browser,True,True,0);self.stack.add_named(panel,'engines')
            self.engine_browser.load_uri(base+'/manage?embedded=1')
        self.stack.set_visible_child_name('engines');self.show()
    def show_log(self):
        if not self.stack.get_child_by_name('logs'):
            panel=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);panel.set_border_width(18)
            row=Gtk.Box(spacing=10);row.pack_start(self.button('← Server overview',self.overview),False,False,0);row.pack_start(self.button('Refresh log',self.show_log),False,False,0);panel.pack_start(row,False,False,0)
            scroll=Gtk.ScrolledWindow();scroll.set_size_request(-1,600)
            self.log_text=Gtk.TextView();self.log_text.set_editable(False);self.log_text.set_monospace(True);self.log_text.set_wrap_mode(Gtk.WrapMode.WORD_CHAR);scroll.add(self.log_text);panel.pack_start(scroll,True,True,0);self.stack.add_named(panel,'logs')
        self.stack.set_visible_child_name('logs');self.show()
        def tail():
            file=root/'server.log'
            if not file.exists():return 'No log entries yet.'
            with file.open('rb') as stream:stream.seek(max(0,file.stat().st_size-100000));return stream.read().decode('utf-8',errors='replace')
        self.work(tail,lambda text:self.log_text.get_buffer().set_text(text))
    def copy(self):
        if self.addresses:Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(self.addresses[0],-1)
    def work(self,operation,done):
        def run():
            try:value=operation();GLib.idle_add(done,value)
            except Exception as error:GLib.idle_add(self.failed,str(error))
        threading.Thread(target=run,daemon=True).start()
    def failed(self,error):self.pending=False;self.message.set_text(error);self.refresh();return False
    def refresh(self):
        if self.checking:return True
        self.checking=True
        def check():
            try:return request('/api/server')
            except Exception:return None
        def apply(info):
            self.checking=False;self.running=info is not None;self.addresses=(info or {}).get('addresses',[])
            self.status.set_text(('Working…' if self.pending else 'Running' if self.running else 'Stopped'))
            self.address.set_text('\n'.join(self.addresses) or 'Start the server to see its address.')
            self.toggle.set_label('Stop server' if self.running else 'Start server')
            self.toggle.set_sensitive(not self.pending);self.restart.set_sensitive(self.running and not self.pending)
            for button in [self.workspace,self.connect_button,self.copy_button]:button.set_sensitive(self.running and not self.pending)
            for title in ['Engine settings','Connect a client']:self.tray_items[title].set_sensitive(self.running and not self.pending)
            self.tray_items['Start server'].set_visible(not self.running);self.tray_items['Stop server'].set_visible(self.running)
            return False
        self.work(check,apply);return True
    def code(self):
        self.show()
        self.work(lambda:request('/api/server/code',True),lambda result:self.code_label.set_text(result['code']))
    def change(self,action):
        if self.pending:return
        self.pending=True;self.message.set_text('Please wait…');self.refresh()
        def run():
            if action in ('stop','restart','quit'):service('stop')
            if action in ('start','restart'):service('start')
            return action
        def done(action):
            self.pending=False;self.message.set_text('');self.code_label.set_text('');self.refresh()
            if action=='quit':self.quit()
            return False
        self.work(run,done)
    def auto_changed(self,button):
        on=button.get_active()
        def run():
            service('enable' if on else 'disable');target=Path.home()/'.config/autostart/ultimate-video-tool-server.desktop'
            if on:target.parent.mkdir(parents=True,exist_ok=True);target.write_text(Path(config['desktopFile']).read_text().replace('open-server-manager.sh"','open-server-manager.sh" --background'))
            else:target.unlink(missing_ok=True)
        self.work(run,lambda _:None)

if __name__=='__main__':Manager().run(sys.argv)
