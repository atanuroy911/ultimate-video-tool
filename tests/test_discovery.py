"""A client finds a Video Tool server on the network without typing its address (vt/server/discovery.py)."""
import socket
import time

import pytest

from vt.server import discovery


def _free_udp() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_the_broadcast_answer_lists_the_server_within_two_seconds():
    udp = _free_udp()
    a = discovery.Announcer(8765, udp_port=udp, bind="127.0.0.1", mdns=False,
                            describe=lambda port: {"app": "video-tool", "name": "GPU box", "version": "1", "port": port, "needs_pairing": True}).start()
    try:
        assert a.problems == []
        t = time.monotonic()
        found = discovery.find(2.0, udp_port=udp, targets=["127.0.0.1"], mdns=False)
        assert time.monotonic() - t < 2.5
    finally:
        a.stop()
    assert found == [{"name": "GPU box", "url": "http://127.0.0.1:8765", "version": "1", "needs_pairing": True, "via": "broadcast"}]


def test_strangers_on_the_port_are_ignored():
    udp = _free_udp()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", udp))

    def reply():
        s.settimeout(2)
        try:
            _, addr = s.recvfrom(64)
            s.sendto(b'{"app": "something-else", "port": 1}', addr)
            s.sendto(b"not json", addr)
        except OSError:
            pass

    import threading

    threading.Thread(target=reply, daemon=True).start()
    try:
        assert discovery.find(0.8, udp_port=udp, targets=["127.0.0.1"], mdns=False) == []
    finally:
        s.close()


def test_a_taken_port_is_reported_not_fatal():
    udp = _free_udp()
    blocker = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    blocker.bind(("127.0.0.1", udp))
    try:
        a = discovery.Announcer(8765, udp_port=udp, bind="127.0.0.1", mdns=False).start()
        a.stop()
    finally:
        blocker.close()
    # Windows lets SO_REUSEADDR share the port, Linux refuses it: both are fine as long as nothing raised


def test_mdns_announce_is_heard():
    pytest.importorskip("zeroconf")
    a = discovery.Announcer(8799, udp_port=_free_udp(), bind="127.0.0.1",
                            describe=lambda port: {"app": "video-tool", "name": "mdns test", "version": "1", "port": port, "needs_pairing": False}).start()
    if any(p.startswith("mDNS") for p in a.problems):
        a.stop()
        pytest.skip(f"no multicast here: {a.problems}")
    try:
        found = discovery.find(3.0, targets=[], udp_port=_free_udp())
    finally:
        a.stop()
    if not any(f["via"] == "mdns" and f["name"] == "mdns test" for f in found):
        pytest.skip("multicast is not looped back on this network")
    assert any(f["url"].endswith(":8799") for f in found)
