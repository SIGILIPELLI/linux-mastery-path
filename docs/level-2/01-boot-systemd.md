---
description: "How a Linux machine boots, from firmware and bootloader through kernel, initramfs and PID 1 to systemd targets, plus the systemctl commands you use daily."
---

# 01 · Booting & systemd Basics

When a Linux server doesn't come back after a reboot, you need to know which stage failed. The boot sequence is a relay: each stage's only job is to find and start the next one. On most
modern distributions the last runner is **systemd**, which also manages services for the rest of the machine's life.

!!! note "What was run"
    Booting and systemd are Linux-only, and this course was written on a Mac with no Linux system, so **nothing in this lesson was run**. The facts come from the
    systemd man pages on man7.org (`systemd.service(5)`, `systemd.timer(5)`, `journald.conf(5)`, read October 2026) and general Linux documentation; distribution defaults vary.
    Lesson 02 contains a unit-file linter that **was** run (it checks text, not a live systemd). See Level 1 · Lesson 01.

## The boot sequence

```text
power on
  → firmware (UEFI, or legacy BIOS)       initialises hardware, finds a boot device
  → bootloader (GRUB, systemd-boot)       loads kernel + initramfs, passes kernel command line
  → kernel                                 initialises CPU, memory, drivers; mounts the initramfs as a temporary root
  → initramfs (initial RAM filesystem)    loads drivers needed to reach the real root (disk, LVM, RAID, encryption); mounts real root
  → PID 1 (systemd)                        starts services in dependency order until the default target is reached
  → login prompt / your services running
```

- **Firmware** reads boot entries from NVRAM (UEFI) and starts a program from the EFI System Partition.
- The **bootloader** presents a menu and loads the chosen kernel with its **command line** (visible in `/proc/cmdline`), for example `root=UUID=... ro quiet`. Editing it at the menu is how you boot into
  single-user/rescue mode (`systemd.unit=rescue.target`, or `init=/bin/bash` as a last resort) when you've locked yourself out.
- The **initramfs** exists because the kernel may need drivers to even read the disk that holds the drivers. After mounting the real root filesystem it hands control to `/sbin/init`, which is a link to systemd on most systems.
- The kernel's messages from boot are in the ring buffer: `dmesg` (or `journalctl -k`).

## systemd in one page

systemd is the init system and service manager: PID 1 for the system. It models everything as **units** with dependencies; the main types:

| Unit type | Suffix | Manages |
|---|---|---|
| Service | `.service` | A daemon or one-shot command |
| Timer | `.timer` | Scheduled activation of another unit (Lesson 02) |
| Socket | `.socket` | A listening socket that starts a service on demand |
| Mount / Automount | `.mount` | A filesystem mount (generated from `/etc/fstab`) |
| Target | `.target` | A named group of units / synchronisation point (like the old runlevels) |
| Path | `.path` | Starts a unit when a file or directory changes |
| Slice / Scope | `.slice` | Resource-control groups (cgroups; Level 3 · 06) |

**Targets** replace runlevels: `multi-user.target` (normal non-graphical server), `graphical.target`, `rescue.target`, `emergency.target`, `poweroff.target`. The default is chosen with `systemctl set-default` and shown by
`systemctl get-default`. When you `enable` a service with `WantedBy=multi-user.target` (Lesson 02), systemd pulls it in when that target is reached.

### Dependencies and ordering are separate

A frequent source of confusion: **`Requires=`/`Wants=` say what should also be started; `After=`/`Before=` say in what order.** If a unit has `Wants=db.service` but no `After=db.service`,
both start at the same time. Most services want both. `Wants=` is a weak dependency (failure of the other doesn't fail you); `Requires=` is hard; `BindsTo=` and `PartOf=` tie lifecycles.
`network.target` only means the networking stack has been *started*, not that you have an address; for "network is actually up", use `After=network-online.target` plus `Wants=network-online.target`.

## The commands you'll use every day (not run)

```bash
systemctl status nginx          # state, recent log lines, main PID, cgroup tree
systemctl start|stop|restart|reload nginx
systemctl enable --now nginx    # start at boot AND start it now
systemctl disable nginx
systemctl is-active nginx; systemctl is-enabled nginx   # script-friendly, with exit codes
systemctl list-units --failed   # what is broken
systemctl list-dependencies multi-user.target
systemctl daemon-reload         # after editing a unit file
systemctl cat nginx             # the unit with all drop-ins merged
systemctl edit nginx            # create a drop-in override (the right way to customise)
journalctl -u nginx -b          # this service's logs, this boot (Lesson 03)
systemd-analyze blame           # which units took longest at boot
systemd-analyze critical-chain  # the chain that determined boot time
```

`enable` and `start` are independent: enabling creates symlinks that take effect at the next boot; starting runs it now (hence `enable --now`). `reload` asks the service to re-read config
(if it supports it) while `restart` stops and starts it. Edit unit files under `/etc/systemd/system/`, never the vendor copies under `/usr/lib/systemd/system/`: use drop-ins
(`/etc/systemd/system/nginx.service.d/override.conf`), which survive package upgrades.

## Troubleshooting boot problems (a method)

1. **Does the kernel start?** No GRUB menu or "no bootable device": firmware or disk problem; use rescue media.
2. **Kernel panic or "unable to mount root fs":** the wrong `root=`, a missing initramfs driver, a corrupt filesystem. Boot an older kernel entry from the bootloader menu; regenerate the initramfs (`update-initramfs -u` / `dracut -f`).
3. **Drops to an emergency shell:** often a bad `/etc/fstab` entry (a missing disk that isn't marked `nofail`) or a filesystem needing `fsck`. Read `journalctl -xb` and fix `fstab` (Lesson 04).
4. **Boots but service missing:** `systemctl --failed`, then `journalctl -u <unit> -b`.
5. **Boots slowly:** `systemd-analyze blame`, usually a network wait or a hung mount.

## How It Actually Works

The kernel starts exactly one userspace program, "init", as PID 1; if it exits the kernel panics. systemd reads unit files, builds a **transaction**: a graph of the units to start plus their ordering
constraints, and starts everything it can in parallel, which is why systemd boots faster than sequential init scripts. Each service runs in its own **cgroup** (Level 3 · 06), which lets systemd track and kill *every*
process a service ever spawned, not just the main PID. Socket activation lets systemd create a listening socket first and start the service on the first connection, so dependent services can start in any
order. The unit's `Type=` (Lesson 02) tells systemd when the service counts as "started", which is the signal other units wait for.

## Common mistakes

- **Editing vendor unit files** in `/usr/lib/systemd/system/` (lost on upgrade); use `systemctl edit`.
- **Forgetting `daemon-reload`** after changing a unit.
- **`After=` without `Wants=`** (or the reverse), getting no ordering or no start.
- **`network.target` as proof the network is up.**
- **A required mount without `nofail`** in fstab that takes the whole boot to emergency mode.
- **Using `enable` and expecting the service to run now.**
- **Rebooting to "fix" a failed service** without reading its log first.

## Exercise

1. On a Linux VM, run `systemd-analyze blame` and `critical-chain`; identify the slowest unit and explain whether it's on the critical path.
2. Write down, for `multi-user.target`, five units it pulls in (`systemctl list-dependencies`), and which dependency is `Wants=` versus `Requires=`.
3. Break a VM on purpose (a bad fstab line), reach the emergency shell, repair it, and record each step. Never do this on a machine you can't rebuild.
4. Use `systemctl cat` on a vendor service and write a drop-in that adds `Restart=on-failure` and `RestartSec=5`. Confirm with `systemctl show -p Restart`.
