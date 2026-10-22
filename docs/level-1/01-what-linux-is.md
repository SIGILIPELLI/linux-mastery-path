---
description: "What Linux actually is: the kernel, the GNU and other userland around it, how distributions differ, and how to tell what you are running."
---

# 01 · What Linux Is: Kernel, Distributions & Userland

"Linux" names two different things, and mixing them up causes a surprising amount of confusion. Strictly, Linux is a **kernel**: the
program that manages the CPU, memory, devices and filesystems, and that every other program asks for services. In everyday speech
"Linux" means a whole operating system built around that kernel, which is really a **distribution**. Knowing where the line sits
tells you what changes when you upgrade, why two Linux machines can behave differently, and where to look when something breaks.

!!! note "About this course and what was run"
    This course was written on a **Mac (macOS, Darwin)** with no Linux machine, virtual machine or container runtime available, so
    **no command here was run on Linux**. What I did instead:

    - Commands that are POSIX-portable (`ls`, `chmod`, `find`, `awk`, pipes, signals, `trap`) were run on macOS, and their output
      is shown labelled "macOS". Where macOS differs from Linux, the difference is a lesson in itself (BSD vs GNU tools).
    - Linux-specific behaviour (`systemctl`, `ip`, `/proc`, `cgroups`, `apt`) is described from the Linux man-pages project
      (man7.org), the kernel documentation and distribution documentation as read in October 2026, and is marked "not run".
    - Programs that parse Linux data are tested against fixture text I wrote to match the documented format, and the fixtures are
      labelled as hand-written.

    A cheap Linux VM, a container, or WSL on Windows lets you run everything yourself. Distribution versions and defaults change, so
    check them against your own system.

## Kernel, userland, distribution

```text
┌──────────────────────────────────────────────────────────────┐
│ Applications: your service, nginx, postgres, a shell          │
├──────────────────────────────────────────────────────────────┤
│ Userland: libc, coreutils (ls, cp), bash, systemd, apt/dnf    │  ← packaged by a DISTRIBUTION
├──────────────────────────────────────────────────────────────┤
│ System-call interface (read, write, mmap, fork, ...)          │
├──────────────────────────────────────────────────────────────┤
│ Linux kernel: scheduler, memory manager, VFS, drivers, TCP/IP │
├──────────────────────────────────────────────────────────────┤
│ Hardware (or a hypervisor presenting virtual hardware)        │
└──────────────────────────────────────────────────────────────┘
```

- The **kernel** runs in privileged mode with direct access to hardware. Programs run in unprivileged *user space* and ask the kernel
  for services through **system calls** (Level 3 · 01).
- **Userland** is everything else: the C library (`glibc` on most distributions, `musl` on Alpine), the core utilities that give
  you `ls` and `cp` (usually the GNU coreutils), a shell, an init system, and a package manager.
- A **distribution** (Debian, Ubuntu, Fedora, RHEL and its rebuilds, Arch, Alpine, SUSE) chooses a kernel version and configuration,
  userland packages, an installer, a package format and a release and support policy.

## Why distributions differ

| Aspect | Debian / Ubuntu family | Fedora / RHEL family | Alpine |
|---|---|---|---|
| Package format and tool | `.deb`, `apt`, `dpkg` | `.rpm`, `dnf`, `rpm` | `.apk`, `apk` |
| C library | glibc | glibc | musl |
| Init system | systemd | systemd | OpenRC |
| Typical use | General servers, desktops | Enterprise servers | Small container images |

That table is general knowledge, not something I verified on a running system, and it changes over time; check your distribution's
documentation. Two practical consequences: a binary built against glibc may not run on musl-based Alpine, and the commands for the same
job (installing a package) differ by family (Lesson 08).

**Kernel versions and the long-term releases.** The kernel project publishes new versions on a regular cadence, and some are designated
long-term support. Distributions ship a particular kernel and often backport fixes, so the version string alone doesn't tell you
which fixes you have. Always check the distribution's security advisories, not just `uname -r`.

## Finding out what you're running

On a Linux machine these are the usual commands (not run here; the macOS equivalent output would not be meaningful):

```bash
uname -srm            # kernel name, release, machine architecture
cat /etc/os-release   # distribution name and version, in a key=value file meant to be sourced
hostnamectl           # on systemd systems: hostname, OS, kernel, virtualization
lscpu; free -h; df -h # CPU, memory and disk summaries
```

`/etc/os-release` is a standard file whose keys (`NAME`, `ID`, `VERSION_ID`, `ID_LIKE`) scripts should use to branch on distribution
(`ID_LIKE=debian` identifies derivatives). Parsing the free-text `/etc/issue` is fragile.

On the Mac used for this course, `uname -s` prints `Darwin`, a reminder that **macOS is not Linux**. It is a BSD-derived Unix with its
own kernel (XNU) and BSD userland. They share POSIX conventions, which is why many commands look identical, and differ in many details
(see Lesson 06). Scripts that must run on both should stick to POSIX features and test on both.

## Everything on top is replaceable

Because the kernel/userland split is clean, you can swap pieces: run a container with a different distribution's userland on the host's kernel
(the container shares the kernel; Level 3 · 06), put Alpine's musl userland in a 5 MB image, or boot the same kernel with a different init
system. It also means a "Linux problem" can live in the kernel (a driver, the OOM killer), in userland (a library version), in the
distribution's configuration (a default firewall) or in your application; the first step of troubleshooting is deciding which layer
(Level 4 · 04).

## How It Actually Works

When you type `ls` in a shell, the shell (a userland program) asks the kernel to create a new process (`fork`/`clone`), then to replace
that process's program with `/bin/ls` (`execve`). The `ls` program calls the C library, which issues system calls: `openat` to open the
directory, `getdents64` to read entries, `write` to print to the terminal. At each call the CPU switches from user mode to kernel mode, the kernel checks
permissions and does the work, then returns to user mode. The kernel never "runs ls"; it provides the services `ls` needs. Everything
Linux-specific in this course follows from that picture: files, processes, permissions, networking, containers and performance tools all
inspect or constrain what the kernel does for programs.

## Common mistakes

- **Saying "Linux" when you mean a distribution** in a bug report. Always include distribution, version and kernel.
- **Assuming macOS commands behave like Linux ones**, or the reverse (Lesson 06).
- **Judging a system's patch level from the kernel version alone.** Backports make version numbers misleading.
- **Parsing `/etc/issue` or `lsb_release` output** instead of `/etc/os-release`.
- **Copying a binary built for glibc onto an Alpine/musl system** and being surprised it won't start.
- **Treating containers as having their own kernel.** They share the host's.

## Exercise

1. On a Linux machine or VM (or WSL), run the four commands above and write down: distribution, version, kernel release, CPU count.
2. Write a shell snippet that sources `/etc/os-release` and prints a different install command (`apt install`, `dnf install`, `apk add`)
   depending on `$ID` and `$ID_LIKE`. Run it on macOS with a fake os-release file to test the branching logic.
3. Find your distribution's support lifecycle page and record when your version stops receiving security updates.
4. Explain, in three sentences, what changes for your applications when only the kernel is upgraded versus only a library.
