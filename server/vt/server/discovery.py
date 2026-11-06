"""Finding a Video Tool server on this network (docs/plans/PLAN-CLIENT-SERVER.MD CS3).

The server announces `_videotool._tcp.local.` over mDNS and also answers one UDP question on port 8767, for networks that block multicast.
A client lists both; typing an address always works as well.

    vt servers                 # what answers on this network, within 2 s
    GET /api/servers           # the same list, for the connection screen
"""
from __future__ import annotations

import json
import socket
import threading
import time
from typing import Any, Callable, Iterable, Optional

SERVICE = "_videotool._tcp.local."
UDP_PORT = 8767
ASK = b"VIDEO-TOOL? 1"


def card(port: int) -> dict[str, Any]:
    """What a server says about itself, here and in `GET /.well-known/video-tool`."""
    from .serve import STATE, VERSION

    return {"app": "video-tool", "name": STATE["name"], "version": VERSION, "port": port}


def _lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


class Announcer:
    """Says "a Video Tool server is here" until stopped. Either half may fail (port taken, no multicast); the other still works."""

    def __init__(self, port: int, *, udp_port: int = UDP_PORT, bind: str = "", mdns: bool = True, describe: Callable[[int], dict] = card):
        self.port, self.udp_port, self.bind, self.mdns, self.describe = port, udp_port, bind, mdns, describe
        self._stop = threading.Event()
        self._sock: Optional[socket.socket] = None
        self._zc: Any = None
        self._info: Any = None
        self.problems: list[str] = []

    def start(self) -> "Announcer":
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.bind, self.udp_port))
            s.settimeout(0.5)
            self._sock = s
            threading.Thread(target=self._answer, name="vt-discovery", daemon=True).start()
        except OSError as e:
            self.problems.append(f"UDP {self.udp_port}: {e}")
        if self.mdns:
            try:
                self._register()
            except Exception as e:                                                      # noqa: BLE001
                self.problems.append(f"mDNS: {e}")
        return self

    def _register(self) -> None:
        from zeroconf import ServiceInfo, Zeroconf

        c = self.describe(self.port)
        host = socket.gethostname().split(".")[0] or "video-tool"
        label = f"{c['name']} ({host})"[:60].replace(".", " ")
        self._info = ServiceInfo(SERVICE, f"{label}.{SERVICE}", port=self.port, addresses=[socket.inet_aton(_lan_ip())],
                                 properties={"name": c["name"], "version": c["version"]},
                                 server=f"{host}.local.")
        self._zc = Zeroconf()
        self._zc.register_service(self._info, allow_name_change=True)

    def _answer(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                data, addr = self._sock.recvfrom(512)
            except socket.timeout:
                continue
            except OSError:
                break
            if data.strip() == ASK:
                try:
                    self._sock.sendto(json.dumps(self.describe(self.port)).encode(), addr)
                except OSError:
                    pass

    def stop(self) -> None:
        self._stop.set()
        if self._sock is not None:
            self._sock.close()
        if self._zc is not None:
            try:
                self._zc.unregister_service(self._info)
            finally:
                self._zc.close()


def _udp(targets: Iterable[str], udp_port: int, until: float) -> list[dict]:
    out = []
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.settimeout(0.2)
    try:
        for t in targets:
            try:
                s.sendto(ASK, (t, udp_port))
            except OSError:
                pass
        while time.monotonic() < until:
            try:
                data, (ip, _) = s.recvfrom(2048)
                c = json.loads(data)
            except socket.timeout:
                continue
            except (OSError, ValueError):
                continue
            if isinstance(c, dict) and c.get("app") == "video-tool" and isinstance(c.get("port"), int):
                out.append({"name": str(c.get("name") or ip), "url": f"http://{ip}:{c['port']}", "version": str(c.get("version", "")), "via": "broadcast"})
    finally:
        s.close()
    return out


def _broadcasts() -> list[str]:
    ip = _lan_ip()
    out = ["255.255.255.255"]
    if ip != "127.0.0.1":
        out.append(ip.rsplit(".", 1)[0] + ".255")             # most home networks are /24; some routers drop the all-ones address
    return out


def find(timeout: float = 2.0, *, udp_port: int = UDP_PORT, targets: Optional[Iterable[str]] = None, mdns: bool = True) -> list[dict]:
    """Every Video Tool server that answers within `timeout`: [{name, url, version, via}], one per address."""
    until = time.monotonic() + timeout
    heard: list[dict] = []
    zc = browser = None
    if mdns:
        try:
            from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf

            def seen(zeroconf, service_type, name, state_change):                      # noqa: ANN001
                if state_change is ServiceStateChange.Added:
                    names.append(name)                  # resolved below: a blocking lookup inside zeroconf's own thread would hang it

            names: list[str] = []
            zc = Zeroconf()
            browser = ServiceBrowser(zc, SERVICE, handlers=[seen])
        except Exception:                                                               # noqa: BLE001
            zc = None
    heard += _udp(_broadcasts() if targets is None else targets, udp_port, until - 0.5 if zc is not None else until)
    if zc is not None:
        browser.cancel()
        for name in dict.fromkeys(names):
            info = zc.get_service_info(SERVICE, name, timeout=max(200, int((until - time.monotonic()) * 1000)))
            if not info or not info.port:
                continue
            props = {k.decode(): (v or b"").decode() for k, v in (info.properties or {}).items()}
            for ip in info.parsed_addresses():
                if ":" not in ip:
                    heard.append({"name": props.get("name") or name.split(".")[0], "url": f"http://{ip}:{info.port}",
                                  "version": props.get("version", ""), "via": "mdns"})
        zc.close()
    out: dict[str, dict] = {}
    for h in heard:
        out.setdefault(h["url"], h)
    return sorted(out.values(), key=lambda h: (h["name"].lower(), h["url"]))
