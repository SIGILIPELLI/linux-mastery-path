---
description: "The Linux network stack: SYN and accept queues, listen backlog (tested on macOS), TIME_WAIT, keepalives, netfilter and key sysctls."
---

# 08 · The Network Stack: Sockets, TCP & netfilter

Network problems on busy servers (dropped connections under load, ports exhausted, "connection reset", mysteriously slow clients) come from limits inside the stack: queues, timers and tables. Knowing the stack's structure tells you which counter to read and which knob matters.

!!! note "What was run"
    The Linux stack (netfilter, `ss -s`, `nstat`, sysctls) was **not run**; values and defaults come from the kernel's `ip-sysctl` documentation (docs.kernel.org, October 2026) and `man7.org` pages. Socket behaviour experiments were run on **macOS**, whose TCP stack is BSD-derived, so queue-overflow behaviour *differs from Linux*, which I flag where it matters. See Level 1 · Lesson 01 and
    Level 2 · Lesson 06 (TCP states, observed).

## The path of a connection (server side)

```text
client SYN ──► [SYN queue: half-open connections]  ──(handshake completes: ACK)──►  [accept queue: established, not yet accept()ed]
                                                                                           │ accept()
                                                                                           ▼
                                                                          application gets a connected socket
```

1. A listening socket has two queues. The **SYN queue** holds connections in `SYN_RECV` (SYN received, SYN-ACK sent, waiting for the client's ACK); its size is limited by `net.ipv4.tcp_max_syn_backlog` ("Maximal number of remembered connection requests ... per-listener limit", per the kernel docs).
2. After the three-way handshake, the connection moves to the **accept queue**, waiting for the application to call `accept()`. Its length is `min(backlog passed to listen(), net.core.somaxconn)`.
3. If the application is too slow to `accept()` (blocked, overloaded, a single-threaded loop busy elsewhere), the accept queue fills and **new connections are dropped or reset**: clients see timeouts, retries and resets, while the server shows low CPU, a classic "it's not busy but nobody can connect" puzzle. On Linux check
   `ss -ltn` (columns `Recv-Q` = current accept queue length, `Send-Q` = its limit for listening sockets) and `nstat -az | grep -i listen` (`TcpExtListenOverflows`, `TcpExtListenDrops`).

### The backlog, tested on macOS

I created a listening socket with `listen(1)` and **never called `accept()`**, then tried 8 connections:

```text
listen(1), never accept(): 1 of 8 connects completed; failures: ['ConnectionResetError'] x7
```

Only one connection was queued (backlog 1); the other seven failed immediately with `ConnectionResetError`. That is **BSD/macOS behaviour: a full queue answers with a reset**. As I understand it, Linux's default behaviour is different: it drops the final ACK or the SYN so the client's connect typically *hangs and retransmits* instead of failing fast, with a `tcp_abort_on_overflow` setting to choose resets instead. I did not run that or re-check it against the
documentation in this session, so treat it as unverified background, not a measurement. The portable lesson: when a server's accept queue overflows, clients see resets or timeouts depending on the OS. Increase `listen()`'s backlog in the application (frameworks default to small values), raise `somaxconn`, and make `accept()` fast (accept in a dedicated thread/loop;
let workers do the slow work).

### SYN floods and syncookies

When the SYN queue overflows, the kernel can answer with **SYN cookies**, encoding state in the sequence number so no memory is held. `net.ipv4.tcp_syncookies` defaults to 1 per the docs, which also warns "it MUST NOT be used to help highly loaded servers to stand against legal connection rate": SYN-flood warnings from legitimate overload mean
tuning the backlog and fixing capacity, not relying on cookies.

## Connection lifecycle costs

- **TIME_WAIT** (Level 2 · 06): the side that closes first holds the connection tuple for about 60 s (the kernel `tcp_fin_timeout` default of 60 s per the docs governs *orphaned FIN_WAIT_2*, a related but different timer). Clients making thousands of short connections to one server IP:port can run out of **ephemeral ports**. The default range
  is `net.ipv4.ip_local_port_range = 32768 60999` per the docs (about 28,000 ports); at 28,000 / 60 s ≈ 470 new connections per second to a single destination you hit the wall unless you reuse connections (keep-alive, connection pools) or widen the range. `tcp_tw_reuse` can allow reuse of TIME_WAIT sockets for *outgoing* connections when safe; the docs' default is 2 (loopback
  only), and note "It should not be changed without advice/request of technical experts." Prefer connection pooling.
- **CLOSE_WAIT** piling up means the application isn't closing sockets after the peer closed (an application bug).
- **Keepalives** detect dead peers on idle connections. Defaults per the kernel docs: `tcp_keepalive_time` 2 hours, `tcp_keepalive_probes` 9, `tcp_keepalive_intvl` 75 s, so a dead idle connection takes over two hours and ~11 more minutes to be noticed. Applications behind NAT/load balancers with shorter idle timeouts (often 350 s or 60 s)
  should enable TCP keepalive with shorter values or use application heartbeats, otherwise connections are silently dropped by the middlebox.
- **Socket buffers** (`net.core.rmem_max`, `net.ipv4.tcp_rmem`, autotuning) bound throughput over high-latency links: throughput ≤ window / RTT, so a 64 KiB window over 100 ms RTT caps at about 5 Mbit/s no matter how fast the link; modern kernels autotune, so manual tuning is rarely needed.

## Where packets can be dropped (checklist)

| Place | Evidence (Linux, not run) |
|---|---|
| NIC ring buffer / driver | `ethtool -S eth0` (rx_dropped, rx_missed), `ip -s link` |
| Kernel backlog (softirq) | `/proc/net/softnet_stat` (dropped column), `nstat` |
| Firewall rule | `nft list ruleset` counters, `-j LOG` entries (Level 2 · 07) |
| Conntrack table full | `dmesg`: `nf_conntrack: table full, dropping packet`; `sysctl net.netfilter.nf_conntrack_max` |
| Listen queue overflow | `ss -ltn` Recv-Q near Send-Q; `nstat` ListenOverflows |
| Application too slow reading | `ss -tn` Recv-Q growing on established sockets |
| Remote/middlebox | `tcpdump`; compare both ends |

`tcpdump -nn -i any port 443 -w cap.pcap` captures packets for analysis with Wireshark; it reveals retransmissions, resets (who sent the RST), and handshake failures that logs can't.

## netfilter: where the firewall hooks in

Packets traverse **hooks**: `prerouting` → (routing decision) → `input` (to local process) or `forward` (to another host) → `postrouting`, and locally generated packets go `output` → `postrouting`. nftables chains attach to these hooks (Level 2 · 07); NAT happens at prerouting (DNAT) and postrouting (SNAT/masquerade) — the basis of Docker's port publishing
and cloud NAT. **conntrack** records flows so NAT can translate replies and `ct state established` rules work; its table has a maximum size, and a busy NAT box or a server with many short flows can fill it, causing silent drops until you raise `nf_conntrack_max` or reduce flows.

## Useful sysctls (defaults only where verified)

| Sysctl | Purpose | Documented default |
|---|---|---|
| `net.core.somaxconn` | Upper bound on `listen()` backlog | (kernel-dependent; check `sysctl`) |
| `net.ipv4.tcp_max_syn_backlog` | SYN queue size per listener | Scales with memory, minimum 128 |
| `net.ipv4.tcp_syncookies` | SYN cookie fallback | 1 |
| `net.ipv4.ip_local_port_range` | Ephemeral ports | 32768 60999 |
| `net.ipv4.tcp_fin_timeout` | Orphaned FIN_WAIT_2 lifetime | 60 s |
| `net.ipv4.tcp_tw_reuse` | Reuse TIME_WAIT for outgoing connections | 2 (loopback only) |
| `net.ipv4.tcp_keepalive_time/_probes/_intvl` | Dead-peer detection | 2 h / 9 / 75 s |
| `net.ipv4.ip_forward` | Route packets between interfaces | (0 on most hosts; Level 2 · Project hardening linter) |

Change with `sysctl -w` and persist in `/etc/sysctl.d/`. **Change one thing at a time with a measurement before and after**; copying a "high performance sysctl" list from a blog post is a common way to make a system worse.

## How It Actually Works

When a SYN arrives, the stack looks up a listening socket by (address, port), creates a lightweight **request socket** in the SYN queue (about 304 bytes each, per the docs) and replies SYN-ACK; when the ACK arrives it allocates a full socket and moves it to the accept queue, waking any process blocked in `accept()`. Data received is placed in the socket's receive buffer; the application's `read()` copies it out, and if
the buffer fills, the advertised TCP window shrinks to zero and the sender stalls (flow control). The stack processes packets in **softirq** context on the CPU that received the interrupt, which is why a single hot flow or a network-heavy host can show one CPU at 100% `si` (software interrupt) time; RSS/RPS and multi-queue NICs spread the load.

## Common mistakes

- **Small `listen()` backlog** in a frameworks' default, then blaming the network.
- **Fixing "too many TIME_WAIT" with risky sysctls** instead of connection reuse.
- **Relying on default keepalives** behind NAT with short idle timeouts.
- **Ignoring conntrack table exhaustion.**
- **Tuning from a copied sysctl list.**
- **Assuming macOS/BSD and Linux behave the same** when a queue overflows (as the test above shows).
- **Looking only at application logs**, when the drop happened in the kernel and left a counter.

## Exercise

1. Reproduce the backlog experiment with a larger backlog and measure how many connections succeed before failure; on Linux also record the failure mode (hang vs reset) and `nstat` counters.
2. Write a client that opens connections to one server as fast as possible until it fails; observe the ephemeral port limit and the number of TIME_WAIT sockets (`ss -tan state time-wait | wc -l`). Then rerun with connection reuse.
3. Using `tcpdump`, capture a failed connection to a closed port and to a filtered (DROP) port; list the packets you see in each case.
4. Compute the maximum throughput for a 256 KiB window over RTTs of 1 ms, 20 ms and 200 ms.
