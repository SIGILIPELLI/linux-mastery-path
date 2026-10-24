---
description: "The Linux network stack from interfaces to routing table, and ip route get tracing a real routing decision for two different destinations."
---

# 01 · The Linux Network Stack: Interfaces, IP & Routing

`ping` either works or it doesn't, and when it doesn't, "is it DNS, is it routing, is it a firewall, is it the
remote host" is the standard troubleshooting ladder — one this lesson and the next few build, starting from the
bottom: what an interface actually is, and how the kernel decides, for *any* destination address, which interface
and which next hop to send a packet through.

## Interfaces and addresses

A network **interface** (`eth0`, `lo`, `wlan0`...) is the kernel's representation of something that can send and
receive packets — a real NIC, a virtual/paravirtualized device (as in this course's VM), or `lo`, the loopback
interface that exists purely so a machine can talk to itself without touching real hardware. An interface can
carry multiple IP addresses, each with a **scope** (`global` — routable beyond this machine; `link` — only valid
on this local network segment, like IPv6 link-local addresses) and, when address assignment comes from DHCP, a
lease duration you can see directly.

## Worked example: a real interface, a real routing table, two real route decisions

```text
$ ip addr show eth0
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 52:55:55:78:ba:7d brd ff:ff:ff:ff:ff:ff
    inet 192.168.5.15/24 metric 200 brd 192.168.5.255 scope global dynamic eth0
       valid_lft 2021sec preferred_lft 2021sec
    inet6 fe80::5055:55ff:fe78:ba7d/64 scope link proto kernel_ll

$ ip route show
default via 192.168.5.2 dev eth0 proto dhcp src 192.168.5.15 metric 200
192.168.5.0/24 dev eth0 proto kernel scope link src 192.168.5.15 metric 200
192.168.5.2 dev eth0 proto dhcp scope link src 192.168.5.15 metric 200

$ ip route get 8.8.8.8
8.8.8.8 via 192.168.5.2 dev eth0 src 192.168.5.15 uid 501
    cache

$ ip route get 1.1.1.1
1.1.1.1 via 192.168.5.2 dev eth0 src 192.168.5.15 uid 501
    cache
```

(Real output from this course's lab VM — a Lima-managed VM, which is why the address range and MAC prefix look
VM-typical rather than like real cloud infrastructure.) `inet 192.168.5.15/24 ... dynamic`: `dynamic` confirms this
address came from DHCP, not static configuration, and the `valid_lft`/`preferred_lft` lease timers are the real
reason a DHCP-assigned address can change later — nothing on this system "owns" this IP permanently. The routing
table has exactly three entries: a route to the local subnet (`192.168.5.0/24`, directly reachable, no gateway
needed), a host route to the gateway itself, and a **default route** (`0.0.0.0/0`, shown as `default`) via
`192.168.5.2` for everything else. `ip route get` shows the kernel's *actual* routing decision for a specific
destination rather than making you read the whole table and reason it out by hand: both `8.8.8.8` (Google's public
DNS) and `1.1.1.1` (Cloudflare's) resolve to the exact same decision — out `eth0`, via the same gateway — because
neither matches the more specific `192.168.5.0/24` route, so both fall through to the default route, which is
exactly what a default route is for.

## How It Actually Works

Routing table lookup is a **longest-prefix match**: the kernel doesn't scan routes in file order, it picks the
route whose destination prefix is the *most specific* match for the packet's destination address, and only falls
back to a less specific (eventually the default, `/0`) route when nothing more specific matches. This is why
`192.168.5.0/24` (a /24, matching 256 addresses) correctly takes priority over the `/0` default route for any
address starting `192.168.5.`, even though both are present in the same table — specificity, not order of
insertion, decides.

`ip route get` doesn't just print a table row back at you — it genuinely runs the kernel's route resolution logic
for that one destination (through the same code path an actual outgoing packet would use) and shows you the
result, including the **source address** the kernel would select (`src 192.168.5.15` here) if you didn't specify
one yourself; on a machine with multiple addresses or interfaces, this source-selection step is itself a real
decision, not an arbitrary pick, and `ip route get <dst> from <specific-src>` lets you ask "what if I wanted to
send from this particular address instead." The `cache` line in the output is a reminder that Linux historically
cached routing decisions for reuse (a performance optimization removed and reworked more than once across kernel
versions); don't read too much into its exact presence or absence across different kernel releases — the
authoritative routing *decision* is always the `via .../dev ...` line above it.

## Common mistakes

- **Assuming `ping` failing means "the network is down."** `ping` tests ICMP reachability specifically, which
  many networks and hosts deliberately block while TCP/UDP traffic flows fine — a failed `ping` with working
  `curl`/`ssh` to the same host usually means a firewall rule (Lesson 3), not a routing or connectivity problem.
- **Confusing `scope link` addresses (like the `fe80::...` IPv6 address above) with globally routable ones.**
  Link-local addresses are only meaningful on the directly-attached network segment and will never appear in a
  routing table as a path to anywhere beyond it.
- **Reading a routing table top-to-bottom and assuming the first matching line wins.** As covered above, the
  kernel selects by most-specific prefix match, not list order — a `/32` host route listed *after* a `/0` default
  route in `ip route show`'s output still wins for its one specific address.

## Exercise

Run `ip addr show` and `ip route show` on any Linux machine, and identify: your default gateway, whether your
main address is static or DHCP-assigned (look for the `dynamic` flag), and your subnet's prefix length. Then run
`ip route get` against three different destinations — one on your local subnet, one well-known public IP, and one
made-up address outside any configured range — and confirm which routing table entry each one actually uses.
