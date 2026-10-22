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
