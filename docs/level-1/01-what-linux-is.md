---
description: "What Linux actually is: kernel vs distro vs userland, monolithic kernel design, and the Unix philosophy that shapes every command you'll learn."
---

# 01 · What Linux Actually Is: Kernel, Distros & the Unix Philosophy

If you've only ever heard "Linux" used as a single word for "the operating system on my server," the first useful
thing to do is split it into three separate layers, because almost every confusing moment later in this course
traces back to mixing them up.

## The three layers

**The kernel** is a single program: a few tens of megabytes of compiled C code that starts running the instant the
bootloader hands it control, and that never stops running until you shut the machine off. It is the only piece of
software that talks directly to the CPU in privileged ("kernel") mode. Its job is narrow but absolute: schedule
processes onto CPUs, manage memory, talk to hardware through drivers, and implement a filesystem abstraction. Every
other program on the system — including `bash`, `systemd`, and `ls` — runs in unprivileged ("user") mode and can
only touch hardware or other processes by asking the kernel to do it on their behalf, through a **system call**.
"Linux" in the strictest sense is just this kernel. You can check which exact kernel build you're running with
`uname -r`.

**The distro** (distribution) is everything built around that kernel to make it a usable operating system: a package
manager, an init system, a standard set of directories, default configuration, and a curated set of packages. Debian,
Ubuntu, Fedora, Arch, and Alpine all ship the *same* kernel source (with different configuration and sometimes
different patches), but they disagree about almost everything above it — how you install software, how services
start, whether `/bin` is a real directory or a symlink into `/usr/bin`. When someone says "Linux behaves differently
on my machine," what's usually different is the distro, not the kernel.

**The userland** is the actual programs you run: the shell, coreutils (`ls`, `cp`, `mv`...), compilers, editors,
servers. Confusingly, most of the core userland on a typical Linux system comes from the **GNU** project, which is
why old-timers insist on calling the whole stack "GNU/Linux" — the kernel is Linux, but a large share of the
command-line tools you use every day are GNU tools, not part of the kernel at all. Alpine Linux swaps GNU's coreutils
and C library for smaller ones (BusyBox and musl), and that single substitution is why some scripts that work
everywhere else quietly break on Alpine (a point the Project in Level 1 and later lessons on package internals will
come back to).

## Worked example: identifying all three layers on a running machine

```text
$ uname -a
Linux lima-linuxlab 7.0.0-34-generic #34-Ubuntu SMP PREEMPT_DYNAMIC Wed Sep  2 14:34:54 UTC 2026 aarch64 GNU/Linux

$ cat /etc/os-release
PRETTY_NAME="Ubuntu 26.04.1 LTS"
NAME="Ubuntu"
VERSION_ID="26.04"
VERSION="26.04.1 LTS (Resolute Raccoon)"
ID=ubuntu
ID_LIKE=debian

$ ldd --version | head -n1
ldd (Ubuntu GLIBC 2.43-2ubuntu2.4) 2.43

$ ls -l /bin
lrwxrwxrwx 1 root root 7 Apr 20  2026 /bin -> usr/bin
```

(Output above is from a real Ubuntu 26.04 LTS "Resolute Raccoon" VM used throughout this course; your own numbers
will differ by kernel build and install date, but the layers you're reading won't.) Four commands, three layers:
`uname -a` reports the **kernel** version (`7.0.0-34-generic`, Ubuntu's build, `aarch64` architecture).
`/etc/os-release` identifies the **distro** (Ubuntu 26.04 LTS) — note the `ID_LIKE=debian` line, itself a clue that
Ubuntu is a Debian derivative sharing much of its packaging approach; this file is a distro convention, not a
kernel feature, and the kernel has no idea what distro it's running inside. `ldd --version` shows which C library
the **userland** is linked against (glibc here, not musl — this matters because statically-linked or musl-linked
binaries behave slightly differently around DNS resolution and locale handling). And `/bin -> usr/bin` shows a
distro-level filesystem layout decision (the "usrmerge"): on modern Debian/Ubuntu/Fedora, `/bin`, `/sbin`, and
`/lib` are just symlinks into their `/usr` equivalents, a cleanup that took over a decade to roll out across distros
and still surprises people who learned Linux from an older book.

## How It Actually Works

The kernel's core design is **monolithic**: the scheduler, memory manager, filesystem code, network stack, and
device drivers all run as one body of code sharing one address space in kernel mode, rather than as separate
services that message each other (the microkernel approach used by, e.g., QNX or seL4). This is a real design
tradeoff. A monolithic kernel is fast — a filesystem read doesn't need to hop between isolated services — but a bug
in one driver can, in principle, crash the whole kernel, because there's no memory boundary between subsystems once
you're inside it. Linux hedges this with **loadable kernel modules** (covered in Level 4): drivers can be compiled
separately and loaded/unloaded at runtime without rebooting, which gives some of a microkernel's modularity without
giving up the monolithic performance model.

The boundary between kernel and userland isn't a style convention — it's enforced by the CPU itself. Modern
processors have hardware privilege levels (x86 calls them "rings," ARM calls them "exception levels"). The kernel
runs at the most privileged level and user programs run at a restricted one; a user program literally cannot execute
an instruction that reconfigures memory protection or talks to a disk controller — the CPU will refuse. The *only*
door between the two is the **syscall** instruction, which the CPU treats as a controlled, well-defined jump into
kernel code at an address the kernel itself chose in advance. This is why `strace` (Level 4) is such a powerful tool:
every single interaction a process has with the outside world — opening a file, reading network data, creating
another process — is a syscall, and tracing them traces everything that program actually does to the system.

## Common mistakes

- **Treating "Linux" and "Ubuntu" (or any distro) as synonyms.** They aren't, and the gap matters the moment you
  work across two distros: a command, package name, default config path, or init system can differ while the kernel
  underneath stays conceptually the same.
- **Assuming GNU tool behavior is universal.** Scripts relying on GNU-specific flags (`sed -i` without a backup
  suffix, certain `date` format strings) can fail silently or differently on BusyBox/musl systems like Alpine or
  embedded distros. If you only ever test on Ubuntu, you will eventually ship a script that breaks somewhere else.
- **Confusing "the kernel crashed" with "a userland program crashed."** A segfaulting application is normal and
  recoverable — the kernel killed one process and everything else keeps running. An actual kernel panic is rare,
  system-wide, and (outside of `dmesg`/serial consoles) usually ends the session; conflating the two leads to
  over- or under-reacting to the wrong kind of failure.

## Exercise

Predict, then run, each of these four commands on any Linux machine (a VM, WSL, or a cheap cloud instance — not
required to be the same distro as this lesson's examples) and write down, for each, which of the three layers
(kernel / distro / userland) it's telling you about: `uname -r`, `cat /etc/os-release`, `which bash` followed by
`file $(which bash)`, and `ls -l /lib64` (or `/lib`, if `/lib64` doesn't exist on your system — note which one your
distro uses, and whether it's a real directory or a symlink).
