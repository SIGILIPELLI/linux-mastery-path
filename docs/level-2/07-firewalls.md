---
description: "Linux firewalls: nftables, iptables, ufw, default-deny design and DROP vs REJECT, with a runnable first-match model showing order mistakes."
---

# 07 · Firewalls: nftables, iptables & ufw

A host firewall decides which packets may reach your services. Linux's packet filtering lives in the kernel (**netfilter**); the tools you use to write rules are front ends. The skill that matters isn't a particular syntax; it's designing a
**default-deny** policy, understanding rule **order**, and not locking yourself out.

!!! note "What was run"
    Firewall rules need Linux and root, so **no `nft`, `iptables` or `ufw` command was run**; syntax is from their man pages and common practice (verify on your distribution). What I ran is a **small Python model of first-match rule evaluation with a default
    policy and connection tracking**. It is a teaching model, not netfilter, and doesn't implement NAT, chains, hooks or most match types. See Level 1 · Lesson 01.

## The tools

| Tool | What it is |
|---|---|
| **netfilter** | The in-kernel framework with hooks in the network stack where packets can be inspected (Level 3 · 08) |
| **nftables** (`nft`) | The modern rule language and tool; successor to iptables; the default backend on current distributions |
| **iptables** | The legacy front end; on many systems `iptables` is now a compatibility layer over nftables |
| **ufw** (Ubuntu), **firewalld** (RHEL family) | Higher-level managers that generate nftables/iptables rules |
| **Cloud security groups** | Network-level filters outside the host (a separate layer; use both) |

Don't mix managers: running ufw, firewalld and hand-written nft rules together produces rules nobody can reason about. Pick one, and write down which.

## Rule evaluation: first match wins, then the policy

For each incoming packet, the chain's rules are checked **top to bottom**; the first matching rule decides (`accept`, `drop`, `reject`). If none match, the chain's **default policy** applies. A secure host sets the input
policy to **drop** and adds explicit accepts. Here is a model of such a ruleset, run with seven test packets:

```python
"""A teaching model of how a stateful packet filter (nftables/iptables style) evaluates rules: first match wins,
a default policy applies, and established connections are accepted by connection tracking. NOT netfilter."""
from dataclasses import dataclass
from ipaddress import ip_address, ip_network

@dataclass
class Packet:
    src: str; dst: str; proto: str; dport: int; iface: str = "eth0"; new: bool = True   # new=False means part of an established flow

@dataclass
class Rule:
    action: str                       # accept | drop | reject
    proto: str | None = None; dport: int | None = None; src: str | None = None
    iface: str | None = None; state: str | None = None  # "established" | "new"
    def matches(self, p: Packet) -> bool:
        if self.proto and p.proto != self.proto: return False
        if self.dport is not None and p.dport != self.dport: return False
        if self.src and ip_address(p.src) not in ip_network(self.src): return False
        if self.iface and p.iface != self.iface: return False
        if self.state == "established" and p.new: return False
        if self.state == "new" and not p.new: return False
        return True

def evaluate(rules, policy, p):
    for i, r in enumerate(rules, 1):
        if r.matches(p): return r.action, f"rule {i}"
    return policy, "default policy"

INPUT = [
    Rule("accept", iface="lo"),
    Rule("accept", state="established"),
    Rule("accept", proto="tcp", dport=22, src="203.0.113.0/24"),     # SSH only from the office range
    Rule("accept", proto="tcp", dport=443),
    Rule("accept", proto="tcp", dport=80),
    Rule("reject", proto="tcp", dport=8080),                          # politely refuse
]
if __name__ == "__main__":
    tests = [
        ("web from anywhere",           Packet("198.51.100.9", "10.0.0.5", "tcp", 443)),
        ("ssh from office",             Packet("203.0.113.40", "10.0.0.5", "tcp", 22)),
        ("ssh from the internet",       Packet("198.51.100.9", "10.0.0.5", "tcp", 22)),
        ("reply on established flow",   Packet("198.51.100.9", "10.0.0.5", "tcp", 51234, new=False)),
        ("postgres from the internet",  Packet("198.51.100.9", "10.0.0.5", "tcp", 5432)),
        ("blocked-with-reject port",    Packet("198.51.100.9", "10.0.0.5", "tcp", 8080)),
        ("loopback anything",           Packet("127.0.0.1", "127.0.0.1", "tcp", 5432, iface="lo")),
    ]
    for name, p in tests:
        a, why = evaluate(INPUT, "drop", p); print(f"{name:<28} -> {a:<6} ({why})")
    print("--- same ruleset, order mistake: a broad rule placed first")
    bad = [Rule("accept", proto="tcp")] + INPUT
    for name, p in tests[2:3] + tests[4:5]:
        a, why = evaluate(bad, "drop", p); print(f"{name:<28} -> {a:<6} ({why})")
    print("--- default policy ACCEPT with no rules")
    print(evaluate([], "accept", tests[4][1]))
```

Output:

```text
web from anywhere            -> accept (rule 4)
ssh from office              -> accept (rule 3)
ssh from the internet        -> drop   (default policy)
reply on established flow    -> accept (rule 2)
postgres from the internet   -> drop   (default policy)
blocked-with-reject port     -> reject (rule 6)
loopback anything            -> accept (rule 1)
--- same ruleset, order mistake: a broad rule placed first
ssh from the internet        -> accept (rule 1)
postgres from the internet   -> accept (rule 1)
--- default policy ACCEPT with no rules
('accept', 'default policy')
```

Read the lessons off the output:

1. **Default deny works**: SSH from the internet and Postgres from the internet match no accept rule, so they hit the `drop` policy. Nothing had to enumerate what to block.
2. **Allowlisting by source** (`ssh` only from the office range) is far safer than exposing SSH to everyone (Lesson 08).
3. **Order is semantics**: put a broad `accept tcp` first and it swallowed the SSH-from-internet and Postgres packets that the specific rules were supposed to restrict. Broad accepts go last; specific denies go first.
4. **Established traffic** must be accepted by a state rule (rule 2), or replies to your own outbound connections get dropped (the host could browse the web but never receive the answers). This is **connection tracking** (`conntrack`): the kernel remembers flows and
   tags packets `new`, `established`, `related` or `invalid`.
5. **Loopback** must be allowed or local services break.
6. A **default ACCEPT policy with no rules** accepts everything, the "firewall" that does nothing.

## DROP vs REJECT

`drop` silently discards the packet: the sender sees a timeout (Lesson 06), scanners learn little, but legitimate clients wait. `reject` sends back an ICMP error or TCP reset: clients fail fast ("connection refused"), which is kinder for internal
networks and makes debugging easier. A reasonable pattern: `drop` on the public internet, `reject` internally.

## A minimal nftables ruleset (not run)

```text
table inet filter {
  chain input {
    type filter hook input priority 0; policy drop;
    iif lo accept
    ct state established,related accept
    ct state invalid drop
    ip protocol icmp accept
    ip6 nexthdr icmpv6 accept
    tcp dport 22 ip saddr 203.0.113.0/24 accept
    tcp dport { 80, 443 } accept
  }
  chain forward { type filter hook forward priority 0; policy drop; }
  chain output  { type filter hook output priority 0; policy accept; }
}
```

Syntax is from the nftables wiki conventions and `nft(8)`; I did not run it. Load with `nft -f /etc/nftables.conf` (and enable the `nftables` service so it persists across reboots). View with `nft list ruleset`. Allowing ICMP/ICMPv6 matters: IPv6 needs neighbour discovery,
and path MTU discovery depends on ICMP, so blocking all ICMP causes strange hangs. And note `output` policy `accept` is common; strict egress filtering is a more advanced control.

ufw equivalent for the same intent:

```bash
sudo ufw default deny incoming; sudo ufw default allow outgoing
sudo ufw allow from 203.0.113.0/24 to any port 22 proto tcp
sudo ufw allow 80,443/tcp
sudo ufw enable ; sudo ufw status verbose
```

## Not locking yourself out

The nightmare: you enable default-deny over SSH and your session dies. Habits: (1) allow SSH *before* enabling; (2) keep a second session open; (3) use a time-bomb rollback:
`(sleep 120 && nft flush ruleset) &` or `at now + 2 min` to revert, then cancel it once you've confirmed access; (4) test on a console-accessible VM first; (5) keep rules in version control and apply them with a
config-management tool (Level 4 · 03). Cloud consoles often give you a serial console as a last resort.

## Rate limiting and logging

nftables can limit new connections (`ct state new limit rate 10/second accept`) and log drops (`log prefix "nft-drop: " counter drop`), which end up in the journal (Lesson 03). Tools like fail2ban read auth logs and add temporary block rules; useful, but not a
substitute for key-only SSH and source allowlists.

## How It Actually Works

Netfilter registers callback functions at fixed points ("hooks") on a packet's path through the kernel: prerouting, input, forward, output, postrouting. An nftables ruleset is compiled into a small bytecode program per chain, attached to a hook; the kernel runs
each packet through the matching chain's rules. The `conntrack` module keeps a hash table of flows keyed by (protocol, source, destination, ports); the first packet of a flow creates an entry in state `new`, and replies match the reverse tuple and are
tagged `established`, so one state rule can admit all legitimate replies without opening ports. Because evaluation is sequential per packet, very long rule lists cost CPU, which is why sets (`{ 80, 443 }`, `ip saddr @allowlist`) and maps exist.

## Common mistakes

- **Default `accept` with a few drops** (a denylist) instead of default drop with accepts.
- **Rule order errors**: a broad accept before a specific restriction.
- **Forgetting loopback or established/related** traffic.
- **Enabling a firewall over SSH without a rollback.**
- **Blocking all ICMP/ICMPv6.**
- **Mixing ufw/firewalld/iptables/nft** managers.
- **Firewalling IPv4 but forgetting IPv6** (or the reverse), leaving the other family wide open.
- **Rules not persisted** across reboot, or persisted without testing the boot-time load.

## Exercise

1. Extend the model with a `related` state and an ICMP rule; add a test that a ping reply is accepted but an unsolicited ping to port-less ICMP type 8 is rate-limited (add a counter).
2. Write the model ruleset for a database server that accepts 5432 only from `10.0.1.0/24` and SSH only from a bastion `10.0.0.10`. Write six tests including two order mistakes.
3. On a Linux VM, apply the nftables ruleset, verify with `nc` from another machine that 22 is dropped from a non-office address, then change `drop` to `reject` for one port and observe the difference in the client's error.
4. Explain why `ct state established,related accept` should usually come before port-specific rules.
