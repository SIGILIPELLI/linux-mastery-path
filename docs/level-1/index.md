---
description: "Linux Level 1: the kernel and distributions, filesystem, links, permissions, users, pipelines, processes, packages, man pages and an audit script."
---

# Level 1 · Linux Foundations

Level 1 builds the vocabulary and the instincts: what the kernel and a distribution are, where things live, what a file really is, who may do what, how to move text through pipelines, how processes start, stop and signal each other, how software is installed, and how to find answers on the machine itself. It ends with a portable audit script and its tests.

!!! note "What was run, and what wasn't"
    This course was written on a **Mac with no Linux machine, VM or container runtime available**, so no command was run on Linux. POSIX-portable behaviour (permissions, links, `find`, pipes, signals, zombies, `trap`) was run on **macOS** and is labelled as such, with the BSD-versus-GNU differences shown as lessons in themselves. Linux-specific facts (`/proc`, `systemctl`, `apt`, `dnf`) come from the Linux
    man-pages project (man7.org), the kernel documentation and distribution documentation as read in October 2026, and are marked "not run". Data that Linux tools would produce is replaced by hand-written fixtures in the documented formats, and labelled. A cheap VM or WSL lets you re-run everything.

**Prerequisites:** a terminal and curiosity. The [Shell Mastery Path](https://sigilipelli.github.io/shell-mastery-path/) covers the shell language in depth; the [Server Ops Mastery Path](https://sigilipelli.github.io/server-ops-mastery-path/) covers deployment and operations practices that build on this course.

## Modules

1. **[What Linux Is](01-what-linux-is.md)**: kernel, userland, distributions.
2. **[The Filesystem Hierarchy & Everything Is a File](02-filesystem-hierarchy.md)**: the tree, devices, file descriptors, redirection order.
3. **[Files, Links & Inodes](03-files-links-inodes.md)**: hard and symbolic links, what `rm` does, `find`, quoting.
4. **[Permissions, umask, setuid & ACLs](04-permissions.md)**: directory `x`, special bits, umask.
5. **[Users, Groups & sudo](05-users-groups-sudo.md)**: identity, the account files, safe sudoers.
6. **[Text Streams, Pipes & Core Tools](06-text-pipelines.md)**: awk, grep, sed, sort and the BSD/GNU traps.
7. **[Processes, Signals & Job Control](07-processes-signals.md)**: zombies, orphans, exit codes, `trap`.
8. **[Package Management](08-package-management.md)**: repositories, signatures, apt vs dnf vs apk.
9. **[Getting Help](09-getting-help.md)**: man sections, builtins vs binaries.
10. **[Project: A Portable System Audit Script](10-project-portable-audit.md)**: a POSIX script with fixture-based tests.

## After Level 1

Level 2 turns these tools into system administration: boot and systemd, services and timers, logging, disks, networking, firewalls, SSH and scheduling, ending with a hardening linter.
