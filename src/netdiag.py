"""Classify why a TCP connection to host:port fails, and time each phase. Uses only the standard library."""
import socket, sys, time

def diagnose(host, port, timeout=3.0):
    result = {"host": host, "port": port}
    t = time.perf_counter()
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        result.update(verdict="DNS_FAILURE", detail=e.strerror, dns_ms=round((time.perf_counter() - t) * 1000, 1)); return result
    result["dns_ms"] = round((time.perf_counter() - t) * 1000, 1)
    family, _, _, _, addr = infos[0]
    result["address"] = addr[0]
    s = socket.socket(family, socket.SOCK_STREAM); s.settimeout(timeout)
    t = time.perf_counter()
    try:
        s.connect(addr)
        result.update(verdict="OPEN", connect_ms=round((time.perf_counter() - t) * 1000, 1))
    except ConnectionRefusedError:
        result.update(verdict="REFUSED", detail="host answered with a reset: nothing listening (or REJECT rule)", connect_ms=round((time.perf_counter() - t) * 1000, 1))
    except ConnectionResetError:
        result.update(verdict="RESET", detail="connection reset during setup: a full accept queue (BSD/macOS) or a middlebox/firewall RST", connect_ms=round((time.perf_counter() - t) * 1000, 1))
    except (socket.timeout, TimeoutError):
        result.update(verdict="TIMEOUT", detail="no answer: packets dropped (firewall DROP, no route, host down)", connect_ms=round((time.perf_counter() - t) * 1000))
    except OSError as e:
        result.update(verdict="ERROR", detail=f"{type(e).__name__}: {e.strerror}", connect_ms=round((time.perf_counter() - t) * 1000, 1))
    finally:
        s.close()
    return result

NEXT = {"DNS_FAILURE": "check /etc/resolv.conf, resolver reachability, the name's spelling, search domains; compare `getent hosts` and `dig`",
        "REFUSED": "check the service is running and listening on that address/port (`ss -ltnp`), bound to 0.0.0.0 not 127.0.0.1, and for REJECT firewall rules",
        "TIMEOUT": "check routes (`ip route get`), firewall DROP rules on both ends and in the network, security groups, and that the host is up",
        "RESET": "check the server accept queue (`ss -ltn` Recv-Q vs Send-Q), the listen backlog, and firewalls or proxies that inject RSTs",
        "OPEN": "TCP works: next layer (TLS, HTTP, auth, application)", "ERROR": "inspect the OS error (e.g. network unreachable = no route)"}

if __name__ == "__main__":
    r = diagnose(sys.argv[1], int(sys.argv[2]), float(sys.argv[3]) if len(sys.argv) > 3 else 3.0)
    print(r); print("next:", NEXT[r["verdict"]])
