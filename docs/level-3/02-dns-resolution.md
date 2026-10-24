---
description: "How Linux actually resolves a hostname: nsswitch.conf's lookup order, resolv.conf, and systemd-resolved's stub resolver, traced on a real query."
---

# 02 · DNS Resolution on Linux: resolv.conf, nsswitch & systemd-resolved

"DNS" is often blamed as a single thing that either works or doesn't, but name resolution on a modern Linux system
actually passes through at least two configuration layers before a single DNS packet goes anywhere — and on most
current distros, `/etc/resolv.conf` doesn't even point at a real DNS server anymore.

## The two layers: nsswitch, then resolv.conf

`/etc/nsswitch.conf`'s `hosts:` line decides, for *any* program calling the standard `getaddrinfo()`/`gethostbyname()`
C library functions, which sources to check and in what order — typically `files dns`, meaning check
`/etc/hosts` first, then fall through to actual DNS. This is why adding an entry to `/etc/hosts` reliably
overrides DNS for that name on a correctly-configured system: it's not a special case, it's `nsswitch.conf`'s
literal, documented order. Only once resolution falls through to the `dns` source does `/etc/resolv.conf` — the
traditional file naming actual nameservers — come into play at all.

## Worked example: a real resolv.conf, nsswitch, and a traced DNS query

```text
$ cat /etc/resolv.conf
# This is /run/systemd/resolve/stub-resolv.conf managed by man:systemd-resolved(8).
# Do not edit.
nameserver 127.0.0.53
options edns0 trust-ad
search .

$ grep ^hosts /etc/nsswitch.conf
hosts:          files dns

$ resolvectl status
Global
         Protocols: -LLMNR +mDNS -DNSOverTLS DNSSEC=no/unsupported
  resolv.conf mode: stub

Link 2 (eth0)
    Current Scopes: DNS
Current DNS Server: 192.168.5.2
       DNS Servers: 192.168.5.2

$ resolvectl query github.com
github.com: 20.207.73.82                                    -- link: eth0
-- Information acquired via protocol DNS in 22.2ms.
-- Data is authenticated: no; Data was acquired via local or encrypted transport: no
-- Data from: network
```

(Real output from this course's lab VM.) The nameserver in `/etc/resolv.conf` is `127.0.0.53` — **localhost**,
not the network's actual DNS server — and the file's own comments explain why: this is systemd-resolved's **stub
resolver**, a tiny local DNS server every program's `getaddrinfo()` call actually talks to. `resolvectl status`
reveals the *real* upstream server, `192.168.5.2` (this network's DHCP-provided gateway/resolver), which
`systemd-resolved` learned automatically and queries on the stub's behalf. `resolvectl query` traces one real
resolution end to end: `github.com` resolved to a real IP in 22.2ms, over plain DNS (not encrypted — `DNSSEC=no`
and "Data is authenticated: no" tell you this network path isn't validating or encrypting DNS responses, worth
knowing before trusting a DNS answer in a hostile network context).

## How It Actually Works

Before `systemd-resolved` became the default on most major distros, `/etc/resolv.conf` really was a flat,
directly-edited file naming real upstream nameservers, and DHCP clients or VPN software would rewrite it directly
whenever network configuration changed — a frequent source of races and clobbered settings when multiple tools
tried to manage the same file. The stub-resolver model fixes this by introducing one stable local point of
contact (`127.0.0.53`, always present, never changes) that every application and library continues to query
exactly as before, while the actual upstream server list, DNSSEC validation, DNS-over-TLS, and per-interface DNS
configuration (useful for VPNs that should only resolve *their own* internal names, not hijack all DNS) are all
managed centrally by the `systemd-resolved` daemon behind that stable stub — `resolvectl status` is how you see
past the stub to what's actually configured.

Crucially, `nsswitch.conf`'s lookup order applies **above** all of this: a program never talks to DNS directly
without first consulting `/etc/hosts` (per the `files` source), and `nsswitch.conf` can name other sources
entirely — `mdns4` for mDNS/".local" name resolution on a LAN, `ldap` in some enterprise directory setups — all
through the exact same pluggable Name Service Switch mechanism, which is why changing how a program resolves
names at the system level never requires touching that program's own code; it's a system-wide, centrally
configured hook every properly-written networked program goes through.

## Common mistakes

- **Editing `/etc/resolv.conf` directly on a `systemd-resolved`-managed system and expecting it to persist.**
  The file's own header warns about this: it's regenerated, and a direct edit is lost on the next network event —
  the supported ways to change DNS servers are `resolvectl` commands, or your network manager's own configuration.
- **Assuming a DNS failure is a DNS server problem without checking `/etc/hosts` and `nsswitch.conf` first.** A
  stale or incorrect `/etc/hosts` entry overrides real DNS silently, by design, per the `files dns` order — it's
  one of the most common "but DNS is clearly working for everyone else" bugs.
- **Trusting plain DNS answers as authenticated.** As `resolvectl query`'s own output shows plainly
  (`Data is authenticated: no`), standard DNS has no built-in integrity guarantee unless DNSSEC validation is
  actually enabled and the response says so — a spoofed answer on an untrusted network is a real risk this output
  format is specifically designed to surface rather than hide.

## Exercise

Run `resolvectl status` on a Linux machine and identify the actual upstream DNS server(s) in use versus the stub
address in `/etc/resolv.conf`. Then add a made-up hostname to `/etc/hosts` pointing at `127.0.0.1`, and confirm
with `getent hosts <that-name>` (which goes through the real `nsswitch.conf`-configured lookup path, unlike
`resolvectl query`, which talks to DNS directly) that it resolves to your override rather than hitting DNS at all.
