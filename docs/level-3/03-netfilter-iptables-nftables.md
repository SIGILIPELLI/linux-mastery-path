---
description: "Netfilter's hooks, how iptables's chains/tables map onto them, and real proof that modern iptables is actually a compatibility shim over nftables."
---

# 03 · Netfilter & Firewalls: iptables vs nftables

"Is `iptables` dead?" comes up constantly, and the honest, slightly surprising answer — provable on your own
machine in one command — is that on most current distros, the `iptables` command still works exactly as always,
but it isn't talking to the old kernel subsystem anymore. It's a compatibility layer over something newer.

## Netfilter: the hooks underneath both tools

**Netfilter** is the kernel subsystem that actually filters, modifies, and routes packets — a set of defined
**hook points** a packet passes through on its journey (`prerouting`, `input`, `forward`, `output`,
`postrouting`), each of which userspace rules can attach to. Neither `iptables` nor `nftables` *is* netfilter;
both are **userspace tools that configure netfilter's hooks**, just with different rule languages and, for the
older tool, an important recent change in what's actually running underneath.

## Worked example: proving iptables is now an nftables frontend

```text
$ iptables -V
iptables v1.8.11 (nf_tables)

$ sudo nft list ruleset
table ip nat {
	chain LIMADNS {
	}

	chain PREROUTING {
		type nat hook prerouting priority dstnat; policy accept;
		counter packets 0 bytes 0 jump LIMADNS
	}
	...
}

$ sudo nft add table inet demo
$ sudo nft add chain inet demo input '{ type filter hook input priority 0 ; }'
$ sudo nft add rule inet demo input ip saddr 10.99.99.99 drop
$ sudo nft list table inet demo
table inet demo {
	chain input {
		type filter hook input priority filter; policy accept;
		ip saddr 10.99.99.99 drop
	}
}
```

(Real output from this course's lab VM.) `iptables -V` literally reports `(nf_tables)` in parentheses — that's
the tool telling you, in its own version string, which kernel backend it's using. On this system, running
`iptables` commands doesn't touch the legacy `x_tables`/`ipt_*` kernel modules at all; it translates your
`iptables`-syntax rule into an equivalent nftables rule behind the scenes. `nft list ruleset` shows this VM's
*actual* firewall/NAT configuration already contains an nftables table named `nat` with a chain called
`LIMADNS` — created not by anything in this lesson, but by Lima's own networking setup, intercepting and
redirecting DNS traffic for the VM. The `add table`/`add chain`/`add rule` sequence then builds a trivial custom
rule directly in nftables's native syntax: a chain attached to the `input` hook, dropping any packet whose source
address is `10.99.99.99` — demonstrating the same hook-attachment model `iptables` itself now compiles down to.

## How It Actually Works

The original `iptables` worked against **`x_tables`**, a kernel framework with a fixed structure: packets flow
through fixed built-in chains (`INPUT`, `OUTPUT`, `FORWARD`...) grouped into fixed tables (`filter`, `nat`,
`mangle`...), and every rule is evaluated by the kernel in sequence for every matching packet — simple, but
inflexible, and increasingly slow on rulesets with thousands of entries because there's no efficient lookup
structure, just a list to walk. **`nftables`**, introduced as x_tables's eventual successor, replaced this with a
small, generic in-kernel virtual machine: rules are compiled into bytecode-like instructions, tables and chains
are entirely user-defined (not fixed names the kernel hardcodes), and set/map data structures allow genuinely fast
matching (checking a packet's source IP against ten thousand addresses in a set is a fast hash lookup, not ten
thousand sequential rule comparisons). The `iptables-nft` compatibility binary (what current distros ship as
plain `iptables`) translates classic `iptables` syntax into equivalent nftables rules at the moment you run it,
specifically so existing scripts, firewall management tools, and institutional muscle memory didn't all have to
be rewritten the day nftables became the default backend.

This matters practically because mixing **legacy** (`iptables-legacy`, still available on most distros as a
separate binary, talking to the old x_tables backend directly) and **nft-backed** (`iptables-nft`) rules on the
same machine can produce a genuinely confusing, partially-inconsistent ruleset — two tools, two different kernel
paths, both claiming to manage "the firewall." `update-alternatives --list iptables` (Debian/Ubuntu) or checking
which binary `iptables` actually resolves to is the way to confirm, with certainty, which backend a given system
is really using before debugging a rule that "should" be working.

## Common mistakes

- **Writing firewall rules in both `iptables` and `nft` syntax on the same machine without checking they're
  using the same backend.** If one is legacy and one is nft-backed, you can end up with two independent,
  overlapping rule sets that don't see or interact with each other at all, each only showing half the picture.
- **Assuming "I don't use `nft` directly, so my firewall doesn't use nftables."** As demonstrated above, that's
  often simply false on a modern distro — checking `iptables -V`'s backend annotation takes one command and
  removes the guesswork.
- **Forgetting that policy order matters within a chain, under both tools.** The first matching rule's action
  (accept/drop/jump) typically takes effect immediately — a broad `accept` rule placed before a more specific
  `drop` rule silently makes the `drop` rule unreachable for traffic the earlier rule already matched.

## Exercise

Run `iptables -V` on a Linux machine you control and check whether it reports an `nf_tables` or `legacy` backend.
Then, in a disposable VM (never on a machine you rely on for connectivity, including over SSH), create a simple
`nft` table/chain/rule that drops traffic from one IP address you don't use, verify it with `nft list ruleset`,
then remove it with `nft delete table`.
