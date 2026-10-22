---
description: "Linux Level 2: systemd, units and timers, logging, disks, LVM and RAID, networking, firewalls, SSH, cron and a hardening linter."
---

# Level 2 · System Administration

Level 2 is the everyday work of keeping a Linux server running: how it boots, how services are defined and supervised, where logs go and why rotation needs a signal, how disks and filesystems are laid out, how RAID's parity actually works, how to reason about addresses, routes, DNS and ports, how to design a default-deny firewall, how to use and harden SSH, and how scheduling really behaves.

!!! note "What was run, and what wasn't"
    Linux-only services (`systemd`, `journald`, `nftables`, `LVM`, `mdadm`, `sshd`) **were not run**; their behaviour is taken from man pages (man7.org) and kernel documentation. What *was* run on macOS: real SSH key generation and inspection, subnet arithmetic with `ipaddress`, real TCP sockets on loopback, a disk image created, formatted and filled, file-descriptor experiments for log rotation, and **tested Python tools** for
    systemd unit files, `fstab`, firewall rule evaluation, RAID parity, cron expressions and hardening. Each lesson says which is which.

**Prerequisites:** Level 1.

## Modules

1. **[Booting & systemd Basics](01-boot-systemd.md)**: the boot relay, units, targets, ordering vs dependency.
2. **[systemd Units, Services & Timers](02-units-timers.md)**: `Type=`, `Restart=`, sandboxing, a tested unit linter.
3. **[Logging: journald, syslog & logrotate](03-logging-journald.md)**: why a rename-rotated log keeps growing.
4. **[Disks, Partitions & Filesystems](04-disks-filesystems.md)**: `fstab`, UUIDs, `nofail`, a tested fstab linter.
5. **[LVM, RAID & Storage Layers](05-lvm-raid.md)**: XOR parity rebuilt in code, and the write hole.
6. **[Networking](06-networking-basics.md)**: CIDR math, routes, DNS, TCP states observed.
7. **[Firewalls](07-firewalls.md)**: first-match rule evaluation and the order mistake.
8. **[SSH: Keys, Config & Hardening](08-ssh-keys.md)**: real keys, `ssh -G`, documented sshd defaults.
9. **[Scheduling: cron, at & Timers](09-scheduling-cron.md)**: the day-of-month OR day-of-week surprise.
10. **[Project: A Server Hardening Linter](10-project-hardening-linter.md)**: sshd, sysctl, fstab and units checked against a baseline.

## After Level 2

Level 3 looks under the hood: system calls, memory, `/proc`, scheduling and load average, I/O, namespaces and cgroups, capabilities, the network stack and a performance method, ending with a `/proc` monitor.
