import socket, threading
from netdiag import diagnose

def test_open_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); s.listen(1)
    r = diagnose("127.0.0.1", s.getsockname()[1]); s.close()
    assert r["verdict"] == "OPEN" and r["connect_ms"] >= 0
def test_refused_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()      # a port that was just freed
    assert diagnose("127.0.0.1", p)["verdict"] == "REFUSED"
def test_dns_failure():
    r = diagnose("no-such-host.invalid", 80); assert r["verdict"] == "DNS_FAILURE"
def test_timeout_on_blackhole():
    # 192.0.2.0/24 is TEST-NET-1 (RFC 5737), reserved for documentation and never routed on the public Internet
    r = diagnose("192.0.2.1", 81, timeout=1.0); assert r["verdict"] in ("TIMEOUT", "ERROR")     # ERROR if the local network has no route at all
def test_backlog_full_resets_or_times_out():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); s.listen(1); p = s.getsockname()[1]
    held = [socket.create_connection(("127.0.0.1", p), timeout=1) for _ in range(1)]
    r = diagnose("127.0.0.1", p, timeout=1.0); s.close()
    assert r["verdict"] in ("OPEN", "REFUSED", "TIMEOUT", "RESET")     # depends on the OS's behaviour when the accept queue is full
