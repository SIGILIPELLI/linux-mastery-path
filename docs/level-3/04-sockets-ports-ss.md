---
description: "What a listening socket actually is, the TCP state machine as seen through ss, and reading real LISTEN and ESTABLISHED connections."
---

# 04 · Sockets, Ports & the ss/netstat Toolset

"Is anything listening on port 8080" and "who is this connection to" are two of the most common first questions
in any networking investigation, and `ss` (the modern replacement for the older `netstat`) answers both directly
from the kernel's live socket table — no packet capture needed, because the kernel already knows exactly what
every socket on the machine is doing.

## What a socket is, and what "listening" means

A **socket** is the kernel's handle for one endpoint of a network conversation — bound to a protocol (TCP/UDP), a
local address and port, and, once connected, a remote address and port too. A socket in **LISTEN** state isn't
connected to anyone; it's a server announcing "I will accept new connections arriving on this port," with the
kernel maintaining a queue of connections that have completed the TCP handshake but haven't yet been `accept()`ed
by the application. A socket in **ESTABLISHED** state is an actual, active, two-way conversation — the pairing
of a specific local address:port with a specific remote address:port is what uniquely identifies it.

## Worked example: real listening sockets and a real established connection

```text
$ sudo ss -tlnp
State  Recv-Q Send-Q Local Address:Port  Peer Address:Port Process
LISTEN 0      4096         0.0.0.0:22         0.0.0.0:*    users:(("systemd",pid=1,fd=277))
LISTEN 0      4096         0.0.0.0:111        0.0.0.0:*    users:(("rpcbind",pid=247297,fd=4))
LISTEN 0      4096   127.0.0.53%lo:53         0.0.0.0:*    users:(("systemd-resolve",pid=231833,fd=21))
LISTEN 0      4096      127.0.0.54:53         0.0.0.0:*    users:(("systemd-resolve",pid=231833,fd=23))

$ python3 -m http.server 8899 --bind 127.0.0.1 &
$ ss -tln | grep 8899
LISTEN 0      5          127.0.0.1:8899       0.0.0.0:*

$ ss -tn state established
Recv-Q Send-Q Local Address:Port  Peer Address:Port
0      0          127.0.0.1:8899     127.0.0.1:38698
0      0          127.0.0.1:38698    127.0.0.1:8899
```

(Real output from this course's lab VM.) The first listing shows real listening sockets and exactly which process
owns each: `sshd` on port 22 bound to `0.0.0.0` (all interfaces), `rpcbind` on 111 (NFS's portmapper, left over
from Lesson 5 of the previous level), and — worth noticing specifically — `systemd-resolve` listening on
**`127.0.0.53` and `127.0.0.54`**, two *different* loopback addresses, both port 53: this is the DNS stub resolver
from Lesson 2, and the second address is a secondary stub used for a specific resolved feature (per-link DNS
scoping) that doesn't matter for this lesson except as proof that "localhost" isn't just one address — `127.0.0.0/8`
is an entire reserved range, and binding different services to different addresses within it is a legitimate way
to keep them from colliding on the same port. The last two lines show one TCP connection from **both sides at
once**: `127.0.0.1:8899` (the server) paired with `127.0.0.1:38698` (the client's **ephemeral port**, picked by
the kernel automatically since the client didn't ask for a specific one) — and the *same pairing*, reversed, as
seen from the client's own socket. One connection, two socket entries, one on each end, both ESTABLISHED.

## How It Actually Works

A TCP connection is uniquely identified by a **4-tuple**: (local IP, local port, remote IP, remote port) — not by
port number alone. This is why a server can hold thousands of simultaneous connections on one listening port 443:
each client connection gets a different remote IP and/or ephemeral port, so the 4-tuple stays unique even though
the *local* half of every one of them is identical (`<server-ip>:443`). The **ephemeral port** range (client-side
ports the kernel assigns automatically, typically somewhere in `32768–60999` on Linux, tunable via
`/proc/sys/net/ipv4/ip_local_port_range`) is what let `38698` appear above without anyone requesting it — the
kernel picked the first available port in that range when the client's socket connected.

TCP's full state machine (`LISTEN`, `SYN_SENT`, `SYN_RECV`, `ESTABLISHED`, `FIN_WAIT1/2`, `CLOSE_WAIT`,
`TIME_WAIT`, `CLOSED`, and a couple of rarer ones) exists because closing a connection is a negotiated,
multi-step process, not an instant drop — which is exactly why `ss -tan` on a busy server will often show
sockets sitting in `TIME_WAIT` (a connection waiting out a safety timer after the application closed it, so any
delayed, duplicate packets from the old connection don't get mistaken for part of a brand-new one reusing the same
4-tuple) or `CLOSE_WAIT` (the *remote* side already closed, but *this* side's application hasn't called `close()`
yet — a large, persistently growing count of `CLOSE_WAIT` sockets is a classic signature of an application that's
leaking connections by never actually closing them).

## Common mistakes

- **Treating a high port number alone as evidence of anything suspicious.** Ephemeral/outbound client ports are
  expected to be high and essentially random — what matters for investigation is the *process* (`-p` flag) and
  the *remote* address, not the local port number of an outbound connection.
- **Confusing LISTEN with ESTABLISHED when reading `ss` output quickly.** A service "listening" on a port being
  present tells you it's ready to accept connections, not that anyone is currently talking to it — `ss -tn state
  established` (as used above) is the right filter for "who's actually connected right now."
- **Ignoring a growing `CLOSE_WAIT` count as "just some old connections."** As explained above, it specifically
  means this side's application hasn't called `close()` on sockets the peer already ended — a real and fixable
  application bug, not a networking quirk.

## Exercise

Run `ss -tlnp` (with `sudo` if needed to see process names) on a Linux machine and identify every listening
service and the process behind it. Then start any simple server (`python3 -m http.server`), connect to it, and
run `ss -tn state established` while the connection is open — identify which side's port is the fixed service
port and which is the ephemeral client port, and explain which 4-tuple field would have to change for the kernel
to allow a second simultaneous connection from the same client.
