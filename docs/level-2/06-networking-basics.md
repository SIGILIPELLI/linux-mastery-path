---
description: "Interfaces, CIDR math, routes, DNS, ports and sockets, with TCP states observed on loopback and ip/ss commands described."
---

# 06 · Networking: Interfaces, Routes, DNS & ss

Most outages that look like "the app is down" are really "the app can't reach something" or "nothing can reach the app". Four questions localise nearly every network problem: **Do I have an address? Do I have a route? Can I resolve
the name? Is something listening on the port?** This lesson builds those four skills.

!!! note "What was run"
    The Linux tools (`ip`, `ss`, `resolvectl`, `nmcli`) were **not run**; they are described from their man pages. What I ran on **macOS**: `ifconfig lo0`, `netstat -rn`, `dig`, `lsof` for sockets, a Python script that opens real TCP sockets on the
    loopback interface and observes their states, and Python's `ipaddress` module for subnet arithmetic. The concepts are identical on Linux; the commands and output formats differ. See Level 1 · Lesson 01.

## 1. Addresses and interfaces

```bash
ip addr                 # (Linux, not run) all interfaces and addresses   (older: ifconfig)
ip -br addr             # brief table
ip link                 # link-layer state (UP/DOWN, MAC, MTU)
ip -4 route; ip -6 route
```

The loopback interface `lo` (named `lo0` on macOS) carries traffic that never leaves the host: `127.0.0.1` (and `::1`). Run on macOS: `ifconfig lo0` printed `flags=8049<UP,LOOPBACK,RUNNING,MULTICAST> mtu 16384` and `inet 127.0.0.1 netmask 0xff000000`: a `/8`
written as a hexadecimal mask on BSD and as `/8` on Linux.

### CIDR and subnets (computed)

An IPv4 address plus a **prefix length** defines a network: `192.168.10.0/26` means the first 26 bits identify the network. Computed with Python's `ipaddress`:

```text
ip_network("192.168.10.0/26") → netmask 255.255.255.192, 64 addresses, network 192.168.10.0, broadcast 192.168.10.63, usable hosts .1 to .62
ip_network("10.0.0.0/24").subnets(new_prefix=26)[1]  → 10.0.0.64/26
ip_address("10.1.2.3") in ip_network("10.0.0.0/8")   → True
ip_address("172.32.0.1").is_private → False      ip_address("172.16.5.5").is_private → True
ip_network("10.0.0.0/23").supernet() → 10.0.0.0/22          ip_interface("192.168.1.77/24").network → 192.168.1.0/24
```

Rules of thumb: usable hosts = 2^(32−prefix) − 2; private IPv4 ranges are `10.0.0.0/8`, `172.16.0.0/12` (so `172.32.x.x` is *public*, as the run shows) and `192.168.0.0/16`; `169.254.0.0/16` is link-local (a DHCP failure sign). Two hosts talk
directly only if they are in the same subnet; otherwise traffic goes to the **default gateway**.

## 2. Routes

A route table maps destinations to next hops. The kernel picks the **most specific (longest prefix) match**.

```text
$ ip route                      (Linux; illustrative, not from a real machine)
default via 192.168.1.1 dev eth0
192.168.1.0/24 dev eth0 proto kernel scope link src 192.168.1.50
```

"Default via" is the gateway for everything not matched elsewhere. `ip route get 8.8.8.8` shows which route and source address the kernel *would* use, the best single test of "do I have a route?". On macOS, `netstat -rn -f inet` prints the equivalent
table (`Destination Gateway Flags Netif`). If you can ping the gateway but nothing beyond it, the problem is upstream; if you can't ping the gateway, look at the link, the VLAN or the address.

## 3. DNS

Names resolve through the C library's resolver, which reads `/etc/nsswitch.conf` (order of sources: `files dns`), `/etc/hosts`, and the DNS servers in `/etc/resolv.conf` (often a stub like `127.0.0.53` on systemd-resolved systems, managed with `resolvectl status`).

```bash
getent hosts example.com        # what the SYSTEM resolver returns (what your programs see)
dig example.com A +short        # what a DNS server returns (bypasses /etc/hosts and nsswitch)
dig @8.8.8.8 example.com        # ask a specific server
dig -x 93.184.216.34            # reverse lookup
```

Run on macOS: `dig +short example.com` returned two IPv4 addresses (addresses of a public site change, so they're not reproduced here). The distinction matters: **`dig` and `ping` can disagree** because `dig` queries DNS directly while
`ping` uses the system resolver, which also consults `/etc/hosts` and caches. Typical DNS failures: wrong or unreachable resolver, search-domain surprises (`search corp.example` appends suffixes), a stale cache, short TTLs.

## 4. Ports, sockets and listening services

A **socket** is an endpoint identified by protocol, address and port. A server `bind`s to an address and port and `listen`s; clients connect from a random **ephemeral** port (49152 to 65535 on macOS by sysctl `net.inet.ip.portrange`; Linux's
`net.ipv4.ip_local_port_range` default is 32768 to 60999, per the kernel documentation, not run here).

```bash
ss -tulpn          # Linux: TCP+UDP, listening, numeric, with owning process (needs root to see other users' processes)
ss -tan state established '( dport = :443 )'
sudo lsof -i :8080 # who owns the port? (portable)
curl -v http://localhost:8080/health   # is the service answering, and what?
nc -zv host 5432                        # can I open a TCP connection to host:port?
```

`0.0.0.0:80` (or `*:80`) means "listening on all IPv4 interfaces"; `127.0.0.1:5432` means **only local clients** can connect, the cause of countless "works on the server, unreachable from outside" tickets. Ports below 1024 are privileged on Linux
(binding needs root or the `CAP_NET_BIND_SERVICE` capability; Level 3 · 07).

### TCP states, observed (run)

I wrote a Python script that opens a listening socket on loopback, connects to it, sends data, closes the client first, then the server, and prints the socket states `lsof` reports at each step. Output:

```text
1. after listen():            {'LISTEN': 1}
2. after connect+accept:      {'LISTEN': 1, 'ESTABLISHED': 2}      (both ends of the connection are on this host)
   server received: b'hi'
3. client closed first:       {'LISTEN': 1, 'CLOSE_WAIT': 1}       (the server end saw the FIN but has not closed yet)
4. server closed too:         {'LISTEN': 1}
5. connect to a closed port:  ConnectionRefusedError - Connection refused
6. bind to a port that is listening: Address already in use
```

- Step 3 is the "CLOSE_WAIT" state, and a **pile of `CLOSE_WAIT` sockets on a server means the application is not closing connections** the peer has closed (a bug in your code, not the network).
- The client side of step 3 was in `FIN_WAIT_2`/`TIME_WAIT`, which `lsof` doesn't show because those sockets no longer have a file descriptor (and `netstat -an` returned nothing in the sandbox I used); on Linux `ss -tan` lists them. Lots of `TIME_WAIT` is normal for busy
  short-connection clients; the state lasts about 60 s on Linux and prevents old packets from corrupting a new connection (Level 3 · 08).
- Step 5, "connection refused", means the host answered with a reset: **nothing is listening** (or a firewall actively rejects). A **timeout** instead means packets are being dropped (firewall `DROP`, wrong route, host down). Telling those apart is the first diagnostic fork (Level 4 · 07).
- Step 6 shows the error you get starting a second server on the same port, or restarting too quickly (`SO_REUSEADDR` mitigates the TIME_WAIT variant).

## A connectivity checklist (not run)

```bash
ip -br addr                   # 1. do I have an address?
ip route get 1.1.1.1          # 2. which route/gateway?
ping -c2 192.168.1.1          # 3. is the gateway reachable? (ICMP may be filtered)
getent hosts example.com      # 4. does the name resolve (system resolver)?
nc -zv example.com 443        # 5. can I open a TCP connection?
curl -sv https://example.com/ -o /dev/null   # 6. does the application layer work (TLS, HTTP)?
```

Work top to bottom; the first failing step names the layer. This is also the shape of the troubleshooting method in Level 4 · 04.

## How It Actually Works

When a program calls `connect()`, the kernel consults the routing table to pick the outgoing interface and source address, assigns an ephemeral port, and starts the TCP three-way handshake (SYN, SYN-ACK, ACK). Packets leave via the interface driver; at the next hop,
the IP address is mapped to a MAC address with ARP (IPv4) or neighbour discovery (IPv6), which you can see with `ip neigh`. On the receiving host the kernel matches the destination port to a listening socket's accept queue (Level 3 · 08) and wakes the process blocked in `accept()`. DNS is not
part of the kernel: it's a library call that sends UDP (or TCP) queries to the configured resolver.

## Common mistakes

- **Binding to `127.0.0.1`** when remote clients must reach the service.
- **Debugging with `dig` when the program uses the system resolver** (or the reverse).
- **Treating a timeout and a refusal as the same failure.**
- **Subnet math off by two** (network and broadcast addresses) or forgetting that `172.16.0.0/12` ends at `172.31.x.x`.
- **Assuming ping works** (ICMP is often blocked).
- **Ignoring IPv6**: a name may resolve to AAAA records and fail where IPv4 works.
- **Not noticing `CLOSE_WAIT` buildup** until file descriptors run out.

## Exercise

1. Use `ipaddress` to design a /16 VPC split into 8 equal subnets; print each subnet's usable range.
2. On Linux, run the six-step checklist against a host you can reach, then block port 443 with a firewall rule on the destination (Lesson 07) and note how step 5 and 6 change (refusal vs timeout, `REJECT` vs `DROP`).
3. Run the TCP script with the server *not* closing its end and count `CLOSE_WAIT` sockets after 100 connections.
4. Find which process listens on a port on your machine, using two different tools, and compare their output.
