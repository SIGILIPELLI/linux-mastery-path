---
description: "Linux Level 3: the network stack, DNS resolution, netfilter/nftables, sockets, SSH internals, SELinux/AppArmor, and namespaces/cgroups."
---

# Level 3 · Networking & Security Internals

Level 3 follows a request from a hostname to a byte on the wire and back, then looks at the kernel mechanisms that
keep processes from stepping on each other: firewalls, mandatory access control, and the namespaces/cgroups pair
that containers are actually built from (no Docker required — you'll build the isolation yourself).

!!! note "What was run, and what wasn't"
    Networking commands (`ip`, `ss`, `dig`/`resolvectl`, `nft`), SSH key generation, and namespace/cgroup commands
    were run on a real Linux VM. SELinux examples are noted as **not run** in this lab — the VM's distribution ships
    AppArmor, not SELinux, which is itself a real and common situation (Ubuntu/Debian default to AppArmor, RHEL/Fedora
    default to SELinux); the SELinux lesson is built from current Red Hat and `selinux-project.org` documentation and
    says so plainly. AppArmor examples are run and real.

**Prerequisites:** Level 1 and 2. Root access inside a disposable VM is assumed for the firewall and namespace
exercises — never run unfamiliar firewall rules on a machine you can't afford to lock yourself out of.

## Modules

1. **[The Linux Network Stack](01-network-stack-routing.md)**: interfaces, IP addresses, the routing table, and
   `ip route get` tracing a real route decision.
2. **[DNS Resolution on Linux](02-dns-resolution.md)**: `/etc/resolv.conf`, `/etc/nsswitch.conf`, and how
   `systemd-resolved` changed the picture.
3. **[Netfilter & Firewalls](03-netfilter-iptables-nftables.md)**: the netfilter hooks, `iptables`'s chains/tables,
   and why `nftables` replaced it.
4. **[Sockets, Ports & the ss/netstat Toolset](04-sockets-ports-ss.md)**: TCP state machine as seen in `ss -tan`,
   and what a listening socket actually is.
5. **[SSH Internals](05-ssh-internals.md)**: host keys vs user keys, `ssh-agent`, and the handshake at a conceptual
   level.
6. **[Linux Security Modules: SELinux vs AppArmor](06-selinux-apparmor.md)**: mandatory access control, labels vs
   path-based profiles, and when each is used.
7. **[Namespaces & Cgroups](07-namespaces-cgroups.md)**: the seven-ish namespace types and the two cgroup
   hierarchies (v1 and v2) that isolate and limit processes.
8. **[Kernel Tuning: sysctl & /proc Parameters](08-sysctl-kernel-tuning.md)**: `/proc/sys`, `sysctl`, and a few
   parameters worth actually knowing.
9. **[Auditing & Hardening](09-auditd-fail2ban-hardening.md)**: `auditd` rules, `fail2ban` jails, and reading a CIS
   benchmark without treating it as gospel.
10. **[Project: Build a Container From Namespaces and Cgroups](10-project-mini-container.md)**: `unshare` + `chroot`
    + a cgroup memory limit, assembled by hand into something that behaves like a (very small) container.

## After Level 3

Level 4 is tools and judgment: tracing and profiling a real process, I/O scheduling, kernel modules, reading `/proc`
and `/sys` as a debugging surface, recovering from a bad boot, and a capstone that builds, hardens and diagnoses a
server from nothing.
