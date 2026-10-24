---
description: "The Linux Filesystem Hierarchy Standard and the virtual filesystems /proc and /sys, which aren't disk files at all but windows into the kernel."
---

# 03 · The Filesystem Hierarchy & Virtual Filesystems (/proc, /sys)

Everything on a Linux system lives under one single tree rooted at `/` — there's no concept of a "C: drive," and a
second disk doesn't get its own letter, it gets *mounted* somewhere inside the existing tree (Level 2 covers
mounting in depth). The Filesystem Hierarchy Standard (FHS) is the convention that says what belongs where, and
once you know it, an unfamiliar Linux system stops being a maze.

## The layout that matters day to day

- **`/etc`** — system-wide configuration, almost always plain text. If you're hunting for "where is X configured,"
  it's under here unless the program is very unusual.
- **`/var`** — data that changes while the system runs: logs (`/var/log`), package manager caches (`/var/cache`),
  spool files, and databases that expect to live on the root filesystem rather than user storage.
- **`/usr`** — the bulk of installed software: `/usr/bin` for programs, `/usr/lib` for libraries, `/usr/share` for
  architecture-independent data (man pages, icons, locale files). On a modern "usrmerge" system (Lesson 1), `/bin`
  and `/lib` are symlinks into here.
- **`/home`** — personal directories for regular users; `/root` is the superuser's home, kept separate on purpose
  so it's never accidentally on a separate, possibly-unavailable mount.
- **`/opt`** — self-contained third-party software that doesn't want to spread its files across `/usr`.
- **`/tmp`** — world-writable temporary storage, usually cleared on reboot and sometimes backed by RAM (`tmpfs`).
- **`/dev`** — device files (Level 2's udev lesson), **`/proc`** and **`/sys`** — covered below.

## Worked example: /proc and /sys are not files on disk

```text
$ stat -f /proc
  File: "/proc"
    ID: 1a00000000 Namelen: 255     Type: proc
Block Size: 4096       Fundamental block size: 4096
Blocks: Total: 0          Free: 0          Available: 0

$ cat /proc/version
Linux version 7.0.0-34-generic (buildd@bos03-arm64-067) (aarch64-linux-gnu-gcc ...) #34-Ubuntu SMP ...

$ cat /proc/cpuinfo | head -n7
processor	: 0
BogoMIPS	: 48.00
Features	: fp asimd evtstrm aes pmull sha1 sha2 crc32 atomics ...
CPU implementer	: 0x61
CPU architecture: 8
CPU variant	: 0x0
CPU part	: 0x000

$ echo $$
10106
$ ls /proc/10106 | head -n8
attr  autogroup  auxv  cgroup  clear_refs  cmdline  comm  coredump_filter

$ cat /proc/10106/status | grep -E "^(Name|State|VmRSS)"
Name:	bash
State:	S (sleeping)
VmRSS:	    5292 kB

$ ls /sys/class/net
eth0  lo

$ cat /sys/class/net/eth0/mtu
1500
```

(Real output, captured on this course's Ubuntu 26.04 ARM64 lab VM — note that ARM's `/proc/cpuinfo` has no
`model name` field at all; that's an x86-specific convention, and ARM instead reports `CPU implementer`/`CPU part`
codes, which is itself a small reminder that `/proc` reflects whatever the *kernel's arch-specific code* chooses
to report, not a fixed universal schema.) `stat -f` reports `/proc`'s filesystem **type** as literally `proc`, not
`ext4` or `tmpfs`, with zero blocks total — it isn't backed by a block device at all. Reading `/proc/version` or
`/proc/cpuinfo` doesn't read bytes off a disk; it triggers kernel code that formats live information into text on
demand, the moment you open the file. `/proc/<pid>/` exists only as long as that process does — `ls /proc/10106`
after that process exits gives "No such file or directory," because there's nothing backing it once the kernel's
internal process-table entry is gone. `/sys` works the same way but is organized by *device and driver* rather than
by process, and — unlike most of `/proc` — many files under `/sys` are genuinely **writable**: writing a new value
to certain files there changes live kernel/driver state immediately (Level 3's `sysctl` lesson uses this directly).

## How It Actually Works

`/proc` and `/sys` are **virtual filesystems** (`procfs` and `sysfs`): the kernel implements the standard
file-operations interface (open, read, write, readdir) for them, but instead of looking up bytes on a disk, each
read calls into kernel code that generates the content at that instant from live, in-memory data structures. This is
a deliberate, elegant design choice: rather than inventing a new API (ioctls, netlink sockets, special syscalls) for
every piece of kernel state someone might want to inspect, the kernel exposes huge amounts of itself through the
one interface every program and script already knows how to use — `open()`, `read()`, `cat`, a shell redirect. It's
why a two-line shell script can read CPU temperature, process memory, or network interface statistics without
linking against any special library.

The split between the two exists mostly for history and API cleanliness. `/proc` is older (the name literally means
*process* information filesystem) and over the decades accumulated system-wide information too (`/proc/cpuinfo`,
`/proc/meminfo`) that has nothing to do with any one process, which the kernel developers eventually considered a
design mistake. `/sysfs` was introduced later specifically to give devices and drivers a clean, consistently
structured place to expose state (and increasingly, tunable parameters you write to, not just read), without
further bloating `/proc`. Both are still around because too much existing software (monitoring tools, container
runtimes reading `/proc/<pid>/cgroup`, `top` itself) depends on `/proc`'s existing layout to ever remove it.

## Common mistakes

- **Treating `/tmp` as a reliable place to store anything you care about.** `systemd-tmpfiles` and many distros'
  defaults clear `/tmp` on every boot, and on some systems `/tmp` is a `tmpfs` mount — data there vanishes not just
  on reboot but is also capped by available RAM.
- **Trying to `cp` or `rsync` `/proc` or `/sys` like normal directories.** File sizes reported for files under
  `/proc` are frequently `0` or wrong (the kernel doesn't know the content's length until it generates it), which
  breaks tools that pre-allocate based on `stat()` size; this is also why you can't meaningfully back up `/proc`.
- **Confusing `/usr/local` with `/usr`.** `/usr` is owned by the package manager — hand-editing files there is
  exactly as fragile as hand-editing `grub.cfg` (Lesson 2) and will be overwritten by the next package update.
  `/usr/local` exists specifically for software you install outside the package manager, so it survives updates.

## Exercise

On any Linux machine, find your shell's own process ID with `echo $$`, then explore `/proc/<that-pid>/` — read
`status`, `cmdline`, and list `fd` (open file descriptors; this previews Lesson 8). Separately, run
`cat /sys/class/net/*/operstate` for every network interface on the machine and match the result (`up`/`down`) to
what `ip link` reports for the same interfaces.
