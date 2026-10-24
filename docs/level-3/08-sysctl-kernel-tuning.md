---
description: "sysctl as a live window into kernel tunables, a real toggle changing kernel behavior instantly, and how persistent config under /etc/sysctl.d works."
---

# 08 · Kernel Tuning: sysctl & /proc Parameters

Level 1 introduced `/proc` and `/sys` as windows into live kernel state, most of it read-only. `sysctl` is the
dedicated, friendlier interface to the *writable* subset of that state — kernel-tunable parameters you can read,
change instantly on a running system, and optionally make persistent across reboots, all without recompiling or
rebooting anything.

## sysctl is just a nicer path to /proc/sys

Every `sysctl` parameter has a direct filesystem equivalent under `/proc/sys/`, with dots in the sysctl name
becoming slashes in the path: `net.ipv4.ip_forward` is exactly `/proc/sys/net/ipv4/ip_forward`. `sysctl` the
command is a convenience layer — nicer names, batch reading, and crucially, support for *persisting* a setting
across reboots via config files — but reading or writing the `/proc/sys` file directly has the identical, immediate
effect, because that's literally the same kernel interface underneath.

## Worked example: a sysctl change taking effect live, no reboot

```text
$ sysctl net.ipv4.ip_forward
net.ipv4.ip_forward = 0

$ cat /proc/sys/net/ipv4/ip_forward
0

$ sudo sysctl -w net.ipv4.ip_forward=1
net.ipv4.ip_forward = 1

$ cat /proc/sys/net/ipv4/ip_forward
1
```

(Real output from this course's lab VM.) `net.ipv4.ip_forward` controls whether this machine's kernel will route
packets *between* interfaces at all (the difference between "an endpoint" and "a router") — flipping it from `0`
to `1` with `sysctl -w` takes effect **immediately**, confirmed by reading the raw `/proc/sys` file right
afterward: no service restart, no reboot, the kernel's packet-forwarding behavior genuinely changed the instant
the write happened.

## Worked example: real persistent configuration

```text
$ ls /etc/sysctl.d/
99-cloudimg-ipv6.conf  99-lima.conf  README.sysctl

$ cat /etc/sysctl.d/99-lima.conf
kernel.unprivileged_userns_clone=1
net.ipv4.ping_group_range = 0 2147483647
net.ipv4.ip_unprivileged_port_start=0
```

(Real output — this is this VM's actual boot-time sysctl configuration, not an illustration.) `99-lima.conf`
exists because this VM needs settings most default installs don't: `kernel.unprivileged_userns_clone=1` lets an
unprivileged user create user namespaces (Lesson 7's `unshare` demo, and anything Lima/container tooling needs,
depend on this), and `net.ipv4.ip_unprivileged_port_start=0` lowers the normally-root-only privileged port
threshold (ports below 1024 traditionally require root to bind) all the way to `0`, so an unprivileged process
inside this VM can bind even classic "privileged" ports like 80 or 443 directly — a deliberate, specific
relaxation this VM's environment needed, not a universal default.

## How It Actually Works

Numbered filename prefixes (`99-lima.conf`) in `/etc/sysctl.d/` aren't decorative — `sysctl` reads every file in
that directory in **lexical filename order** and applies them in sequence, so a later-processed file's setting for
the same key wins over an earlier one; the convention of prefixing with numbers (lower numbers processed first,
so they can be safely overridden by higher-numbered, more specific files) exists to make override order
predictable without needing to read every file's content to know which one "wins." This is the same pattern
`/etc/apt/apt.conf.d/`, `systemd` drop-in directories, and many other Linux configuration systems use — a
deliberate design convention, not something specific to sysctl.

Not every kernel parameter can be changed live this way. Some are genuinely runtime-adjustable (like
`ip_forward`, which the kernel can safely act on differently from one packet to the next); others only take
effect at boot or module-load time and are exposed read-only or write-once (a parameter's own documentation, or
simply trying a write and checking the result, is the way to find out which kind you're dealing with — there's
no single flag in the output distinguishing them). This matters because tuning guides sometimes suggest a
`sysctl -w` change "to test it," and for boot-time-only parameters that test is silently meaningless — the write
may succeed without the running kernel actually behaving differently until the next boot.

## Common mistakes

- **Changing a sysctl live with `sysctl -w` and forgetting it reverts on reboot.** Unless the same value is also
  written into a file under `/etc/sysctl.d/` (and `sysctl --system` or a reboot applies it), a live change is
  temporary — a classic source of "it worked yesterday and now it's back to broken" confusion after a maintenance
  reboot.
- **Editing multiple sysctl.d files with conflicting settings for the same key and not checking processing
  order.** As covered above, lexical filename order decides the winner — `sysctl --system` with verbose output
  shows exactly which file's value for each key was actually applied last.
- **Assuming a networking sysctl change takes effect for already-established connections.** Many networking
  parameters (buffer sizes, certain TCP behaviors) only apply to *new* connections or sockets created after the
  change — existing ones keep whatever was in effect when they were created.

## Exercise

Run `sysctl vm.swappiness` and `sysctl net.ipv4.ip_forward` on a Linux machine you control, and read both values'
meanings from the kernel documentation. Then check `/etc/sysctl.d/` for any files already there, read what each
one changes and why (often there's a comment explaining the reason), and identify whether any of them rely on the
filename-ordering behavior to override an earlier file's setting.
