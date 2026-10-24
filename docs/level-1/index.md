---
description: "Linux Level 1: what the kernel does, boot, the filesystem hierarchy, inodes, the permission model, processes 101 and package internals."
---

# Level 1 · The Kernel, Filesystem & Permissions

Level 1 builds the mental model everything else sits on: what the kernel actually is, how a machine gets from power-on
to a login prompt, how the filesystem is laid out and how it really stores a file (not "in a folder" but as an inode
with data blocks), what a permission bit actually gates, what a process is before it's even run anything, and how a
package manager tracks what's installed. Every command in this level was run against a real Linux kernel, not guessed
from documentation.

!!! note "What was run, and what wasn't"
    This course was written and verified on a Debian/Ubuntu Linux virtual machine (an ARM64 VM running under Lima/QEMU
    on macOS, with the same kernel and userland you'd get from a cloud VM). Every `ls`, `stat`, `ps`, `ps -ef --forest`,
    `ls -i`, `ln`, `chmod`, `useradd`, `dpkg -L`, and boot-log excerpt shown was actually run and its real output is
    shown, trimmed for length where noted. Where a lesson talks about a different distro's package manager (RPM/DNF)
    or a mechanism the lab VM's provisioning didn't expose (actual UEFI firmware, a non-systemd init), it says so and
    draws on the vendor documentation instead of a fabricated run.

**Prerequisites:** comfort typing commands in a terminal (`cd`, `ls`, editing a file). No prior Linux internals
knowledge assumed. If you want the shell scripting language itself — variables, loops, `sed`/`awk` — that's the
[Shell/Bash Mastery Path](https://sigilipelli.github.io/shell-mastery-path/); this course treats the shell only as
the window you're typing commands into.

## Modules

1. **[What Linux Actually Is](01-what-linux-is.md)**: kernel vs distro vs userland, the Unix philosophy, monolithic
   vs microkernel, why "Linux" means dozens of different operating systems.
2. **[The Boot Process](02-boot-process.md)**: firmware (BIOS/UEFI), the bootloader, the kernel and initramfs,
   switching root, and the first userspace process.
3. **[The Filesystem Hierarchy & Virtual Filesystems](03-filesystem-hierarchy.md)**: the FHS layout (`/etc`, `/var`,
   `/usr`...), and the kernel-generated filesystems `/proc` and `/sys` that aren't really files at all.
4. **[Files, Inodes & Links](04-inodes-links.md)**: what an inode holds, how a directory is just a name-to-inode
   table, and the real difference between a hard link and a symlink.
5. **[Users, Groups & the Permission Model](05-users-permissions.md)**: UIDs/GIDs, `rwx` on files vs directories,
   `umask`, and why a directory's execute bit means something different from a file's.
6. **[Advanced Permissions: SUID, SGID, Sticky Bit & ACLs](06-suid-sgid-acls.md)**: how `passwd` lets you change your
   own password, the sticky bit on `/tmp`, and POSIX ACLs for when owner/group/other isn't enough.
7. **[Processes 101](07-processes-101.md)**: PIDs and PPIDs, `fork`/`exec`, the process tree, and what PID 1 actually
   does.
8. **[Standard Streams, File Descriptors & Pipes](08-streams-descriptors-pipes.md)**: fd 0/1/2 as kernel-level file
   table entries, what a pipe actually is, and why redirection order matters.
9. **[Package Management Internals](09-package-management-internals.md)**: what `dpkg`/APT and `rpm`/DNF actually
   track, dependency resolution, and what a package "install" really writes to disk.
10. **[Project: Build and Boot a Minimal Root Filesystem](10-project-minimal-rootfs.md)**: assemble a bare root
    filesystem by hand with `debootstrap` and `chroot` into it, so "what does an OS actually need to boot" stops
    being abstract.

## After Level 1

Level 2 moves from reading the system to managing it while it's running: signals and process states, the scheduler,
virtual memory and the OOM killer, disks and LVM, and `systemd` — units, services, timers and logs.
