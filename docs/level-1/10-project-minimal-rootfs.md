---
description: "Project: assemble a minimal root filesystem with debootstrap and chroot into it, to see concretely what an OS actually needs to run."
---

# 10 · Project: Build and Boot a Minimal Root Filesystem

Every lesson in this level talked about the filesystem hierarchy, permissions, and processes as properties of
*the* system you're logged into. This project builds a second, completely independent root filesystem from
nothing but a package tool and a network connection, and uses `chroot` to run commands inside it — which forces
"what does an OS actually need before it's usable" to stop being abstract.

## What debootstrap actually does

`debootstrap` is the tool Debian/Ubuntu installers use internally: given a target directory, a release codename,
and a package mirror, it downloads and unpacks just enough `.deb` packages to produce a minimal, bootable-in-spirit
root filesystem — without needing to actually boot anything. It runs in two stages: an initial unpack of core
packages, then a **second stage that runs inside the new filesystem via `chroot`**, so that package postinst
scripts (Lesson 9) execute in the correct environment rather than against the host.

## Building it

```text
$ sudo debootstrap --variant=minbase --arch=arm64 noble /tmp/minirootfs http://ports.ubuntu.com/ubuntu-ports
I: Configuring libstdc++6:arm64...
...
I: Configuring apt...
I: Configuring libc-bin...
I: Base system installed successfully.
```

(Real output from this course's lab VM — this command genuinely downloads and assembles a working minimal Ubuntu
24.04 "Noble" filesystem; expect it to take a few minutes depending on your network.) `--variant=minbase` asks for
the smallest useful set of packages rather than a full default install; `--arch=arm64` matches this course's lab
VM (use your own machine's architecture, or cross-build a different one, which is exactly how you'd prepare a root
filesystem for, say, a Raspberry Pi from an x86 desktop).

## Entering it

```text
$ sudo mount --bind /dev /tmp/minirootfs/dev
$ sudo mount -t proc proc /tmp/minirootfs/proc
$ sudo mount -t sysfs sys /tmp/minirootfs/sys

$ sudo chroot /tmp/minirootfs /bin/bash -c "
    cat /etc/os-release
    echo hostname-in-chroot: \$(hostname)
    echo whoami: \$(whoami)
    ls /bin | wc -l
    apt list --installed 2>/dev/null | wc -l
"
PRETTY_NAME="Ubuntu 24.04 LTS"
NAME="Ubuntu"
VERSION_ID="24.04"
VERSION="24.04 LTS (Noble Numbat)"
ID=ubuntu
hostname-in-chroot: lima-linuxlab
whoami: root
293
91
```

(Real output.) `cat /etc/os-release` reports **Noble 24.04** — a different, self-contained distro release from the
26.04 LTS host VM this project is running on — proving the new root filesystem really is independent, not a view
into the host's own files. `hostname` reports the *host's* hostname, `lima-linuxlab` — because plain `chroot`
changes only which directory a process treats as `/`; it does **not** create a new UTS namespace (the kernel
mechanism that isolates hostname), so the chrooted shell still sees the real machine's hostname. 293 binaries and
91 packages is the entire footprint of a "minimal" Debian-family Linux system — small enough to read through
`dpkg -l` in a few minutes, which is itself worth doing once, just to see what's actually considered load-bearing.

## What breaks without the bind mounts, and why that's the lesson

```text
$ sudo umount /tmp/minirootfs/proc /tmp/minirootfs/sys /tmp/minirootfs/dev
$ sudo chroot /tmp/minirootfs /bin/bash -c "ps aux"
Error, do this: mount -t proc proc /proc

$ sudo chroot /tmp/minirootfs /bin/bash -c "uname -a"
Linux lima-linuxlab 7.0.0-34-generic ... aarch64 aarch64 aarch64 GNU/Linux
$ uname -a
Linux lima-linuxlab 7.0.0-34-generic ... aarch64 GNU/Linux
```

(Real output.) Unmounting `/proc` and re-running `ps` inside the chroot fails outright — `ps` has nothing to read,
because `/proc` isn't automatically present inside a chroot; it has to be deliberately mounted there, which is
exactly why the earlier bind-mount step exists at all and why debootstrap's own second stage does the same thing
internally. The second pair of commands is the project's real payoff: `uname -a` **inside** the chroot and on the
**host** report the identical kernel release, `7.0.0-34-generic`. `chroot` did not boot a new kernel, did not boot
anything at all — the minimal root filesystem is running entirely on the one kernel the host machine was already
running, with a different `/` underneath it. That's the whole mechanism behind `chroot`, and it's also most of the
mechanism behind how container runtimes work before you add namespaces and cgroups on top (Level 3's `namespaces`
lesson builds exactly that on top of this same foundation).

## How It Actually Works

A `chroot()` syscall records a new "root directory" pointer in the calling process's kernel-level process
descriptor; every subsequent path resolution that starts from `/` for that process (and, after `fork()`, its
descendants) resolves relative to that recorded directory instead of the real filesystem root. Nothing about
memory, networking, process visibility, users, or the kernel itself changes — which is precisely why plain `chroot`
is **not** a security boundary (a well-known escape technique for a process running as root inside a chroot is to
open a file descriptor to a directory outside it before the chroot call, then use that descriptor afterward) and
why modern container tooling layers PID, network, mount, and user **namespaces** (Level 3) on top of the same
`chroot`-style root-swapping to get real isolation.

## Common mistakes

- **Forgetting the bind mounts and assuming the rootfs is "broken."** `ps`, `df`, networking tools, and anything
  reading `/proc` or `/sys` will fail or behave strangely without those filesystems explicitly mounted inside the
  chroot — this is expected, not a sign the build failed.
- **Treating `chroot` as a security sandbox.** As covered above, it isolates the filesystem view only; a
  privileged process can escape it, and an unprivileged one can still see and potentially signal processes outside
  it, since there's no PID namespace involved.
- **Not cleaning up bind mounts before deleting the rootfs directory.** `rm -rf` on a directory with `/proc`,
  `/sys`, or `/dev` still bind-mounted inside it can delete far more than intended (or fail oddly) — always
  `umount` each bind mount first.

## Exercise

Build your own minimal root filesystem with `debootstrap` (or `pacstrap` on Arch, or a manual `rpm --root`
bootstrap on Fedora, if you'd rather use a different family). Chroot into it, confirm `uname -a` matches your host
kernel exactly, then try running a statically-linked binary you copy in from outside versus a dynamically-linked
one — the dynamic one will fail unless its required shared libraries also exist inside the chroot, which is a
direct, hands-on demonstration of what "dependency" really means at the binary level, not just the package level
from Lesson 9.
