---
description: "Network faults by symptom: DNS failure vs refused vs timeout vs reset (reproduced and classified in code), curl timing, MTU and tcpdump."
---

# 07 · Troubleshooting the Network

Network problems feel mysterious because the symptom ("can't connect") is the same for a dozen different causes. The key skill is to **classify the failure** from its exact shape: does the name not resolve, does the host actively refuse, does nothing answer at all, or does the connection die mid-way? Each points to a different layer and fix.

!!! note "What was run"
    The classification code, `curl` timing/exit-code experiments and the local servers ran on **macOS** (Python 3, curl, the loopback interface, and the reserved documentation address `192.0.2.1` for a timeout, which is never routed on the public internet). Linux tools (`ip`, `ss`, `tcpdump`, `mtr`, `ethtool`) were **not run**; they are described from their documentation. macOS and Linux TCP stacks differ in details such as how a full accept queue
    behaves (Level 3 · 08). See Level 1 · Lesson 01.

## The four fundamental failure shapes (reproduced)

I wrote a small standard-library Python tool that connects to `host:port`, times DNS and connect separately, and classifies the outcome. Run against four targets:

```text
127.0.0.1:<listening port>   OPEN         dns 2.2 ms, connect 0.2 ms
127.0.0.1:1                  REFUSED      dns 0.0 ms, connect 0.1 ms      "host answered with a reset: nothing listening (or REJECT rule)"
no-such-host.invalid:443     DNS_FAILURE  dns 1.4 ms                       "nodename nor servname provided, or not known"
192.0.2.1:81                 TIMEOUT      dns 0.6 ms, connect 1502 ms      "no answer: packets dropped (firewall DROP, no route, host down)"
```

The most important contrast is **REFUSED vs TIMEOUT**. A refusal took 0.1 ms: the target host replied immediately with a reset, so the network path works and *no process is listening there* (or a firewall `REJECT`s). The timeout waited the full 1.5 s limit: no reply at all, which means packets are being dropped somewhere (firewall `DROP`, security group, missing route, host down). They have very different fixes, and confusing them wastes hours.
A fifth outcome, `RESET`, appears when the connection is reset during setup: in my earlier backlog experiment (Level 3 · 08) a full accept queue on macOS produced `ConnectionResetError`; it can also come from firewalls or proxies that inject resets.

```python
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
```

The five pytest tests (open, refused, DNS failure, timeout on the blackhole, full-backlog) pass. One of my tests initially failed: I had assumed a full accept queue always produced a refusal or timeout, but on macOS it produced a reset. The test was wrong about the OS, and I added `RESET` as a verdict: a small example of why network tools should be validated on the platform you run them on.

## What curl tells you

`curl` is a network diagnostic tool as much as an HTTP client. Timing variables split a request into phases:

```bash
curl -s -o /dev/null -w "dns=%{time_namelookup}s connect=%{time_connect}s ttfb=%{time_starttransfer}s total=%{time_total}s http=%{http_code} size=%{size_download}\n" http://127.0.0.1:8765/index.html
```

Run against a Python test server on loopback:

```text
dns=0.000152s connect=0.000532s ttfb=0.008136s total=0.008225s http=200 size=6
missing page -> http=404
```

Read them cumulatively: `connect` includes DNS; `time_appconnect` (for HTTPS) adds TLS; `time_starttransfer` (TTFB) adds the server's thinking time. A slow `dns` means resolver trouble, a slow `connect` means network latency or SYN drops and retransmits, a slow TTFB with a fast connect means the **application** is slow, and a slow total with a fast TTFB means a big or slow transfer. The HTTP status is a separate layer: the server responded (404 here), so the network is fine.

**Curl exit codes** classify failures too. Run on the same three bad targets: closed port → exit **7** (`Failed to connect`), blackholed address with `-m 2` → exit **28** (operation timed out), unresolvable name → exit **6** (`Could not resolve host`). Others worth knowing: 35 (TLS handshake failure), 51/60 (certificate problems), 52 (empty reply), 56 (connection reset while receiving). Use `curl -v` to see the whole conversation (DNS, TLS, request and response headers) and `--resolve host:443:IP` to test a specific backend without changing DNS.

## A layered checklist (Linux; not run)

| Layer | Question | Commands |
|---|---|---|
| Link | Is the interface up and carrying packets? | `ip -br link`, `ethtool eth0` (speed, duplex, link detected), `ip -s link` (errors/drops) |
| IP | Do I have an address and a route? | `ip -br addr`, `ip route get <dst>` |
| Neighbour | Can I reach the gateway at layer 2? | `ip neigh` (REACHABLE vs FAILED/STALE), `arping` |
| Path | Where does it stop? MTU? | `ping -c3 gw`, `mtr -rwc 20 host`, `ping -M do -s 1472 host` (path MTU test), `traceroute` |
| Name | Does DNS resolve, and consistently? | `getent hosts name`, `dig +trace name`, `resolvectl query name` |
| Transport | Is the port reachable? | `nc -zv host port`, the classifier above |
| Security | Is a firewall in the way? | `nft list ruleset`, cloud security groups, `tcpdump` on both ends |
| TLS | Handshake and certificate OK? | `openssl s_client -connect host:443 -servername host`, `curl -v` |
| Application | Does it respond correctly? | `curl`, application logs |

Always test from **both sides** and from a second client: a problem visible from one client only is about that client's path or config. Compare against a known-good host.

### MTU and "works for small, hangs for large"

If small requests succeed and large ones hang, suspect **path MTU**: a link in the path has a smaller MTU (tunnels, VPNs, overlay networks, jumbo frames mismatched) and fragmentation-needed ICMP messages are being blocked, so large packets vanish silently. Test with ping and the don't-fragment flag at decreasing sizes; fix by correcting the MTU or MSS (`iptables`/`nft` MSS clamping) and by not blocking ICMP (Level 2 · 07).

### Packet capture

`tcpdump` shows what actually crossed the wire:

```bash
sudo tcpdump -nn -i any 'host 10.0.2.15 and port 5432' -c 50          # watch a connection attempt
sudo tcpdump -nn -i eth0 'tcp[tcpflags] & (tcp-syn|tcp-rst) != 0'     # only SYNs and RSTs
sudo tcpdump -i any -w cap.pcap port 443                              # save for Wireshark
```

Interpreting a failed connection: **SYN, SYN-ACK, ACK** is a healthy handshake; **SYN with no reply** (repeated SYNs, backing off at 1, 2, 4... seconds) is a drop or no route; **SYN then RST** is a refusal; **SYN, SYN-ACK, then RST from the client** often means the client rejected it (asymmetric routing: replies arrive from a different address). Capture on both client and server: if the SYN appears on the client but never on the server, the problem is in between. Mind privacy: captures contain data.

## Intermittent problems

Intermittency suggests: one bad backend among several behind a load balancer (test each directly), DNS returning multiple IPs with one dead, connection reuse hitting idle timeouts in a NAT/load balancer (keepalives, Level 3 · 08), conntrack table full, ephemeral port exhaustion, packet loss on a link (`mtr` shows loss per hop; loss only at a middle hop that doesn't continue is usually ICMP rate limiting, not real loss), or periodic jobs saturating a link. Log timestamps and correlate.

## How It Actually Works

A refused connection is an *answer*: the destination's kernel received the SYN, found no listening socket for that address and port, and sent back a TCP reset. A timeout is the absence of an answer: either the SYN never arrived, or the reply never came back, or a middlebox dropped it silently, and the client retransmits with exponential backoff until its own timer fires. DNS failure happens before any packet to the destination: the resolver's own query got `NXDOMAIN`,
no answer, or an error. This is why the cheap classification works: each shape comes from a different component of the path, and your OS's error codes (`ECONNREFUSED`, `ETIMEDOUT`, `ENETUNREACH`, `EHOSTUNREACH`, `ECONNRESET`) preserve it, as do `curl`'s exit codes.

## Common mistakes

- **Treating timeout and refused as the same.**
- **Testing only from the server itself** (localhost works, remote doesn't: a bind address or firewall issue).
- **Trusting `ping`** as proof of service health (ICMP is not TCP, and may be blocked or allowed independently).
- **Debugging DNS with the wrong tool** (`dig` vs the system resolver).
- **Forgetting IPv6 / AAAA records**, so clients try an unreachable IPv6 address first.
- **Capturing on only one side.**
- **Ignoring MTU** in tunnel/overlay setups.
- **Blocking all ICMP.**

## Exercise

1. Run the classifier against five hosts of your own (a working service, a stopped service, a closed firewall port with DROP, with REJECT, and a made-up name); record the verdict and timing for each. On Linux, confirm the DROP/REJECT difference in `tcpdump`.
2. Use `curl -w` to build a timing report for a real HTTPS site and identify which phase dominates; repeat three times and note the variance.
3. Create a path-MTU black hole on a test VM (lower the MTU on one hop, block ICMP) and demonstrate "small works, large hangs", then fix it.
4. Extend the tool to try each address returned by DNS (IPv4 and IPv6) and report which ones fail.
