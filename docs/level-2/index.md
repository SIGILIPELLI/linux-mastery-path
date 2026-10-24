---
description: "Linux Level 2: signals, the CFS scheduler, virtual memory and the OOM killer, disks/LVM, mounting, and systemd units, services, timers and journald."
---

# Level 2 · Processes, Memory & Storage

Level 2 is about a system that's running, not just installed. You'll send real signals and watch processes change
state, read `/proc/<pid>/status` to see what the kernel actually tracks about a process, trigger an OOM kill on
purpose, partition and mount a disk with LVM, and write your own `systemd` unit files instead of only reading ones
someone else wrote.

!!! note "What was run, and what wasn't"
    Process, memory, disk and `systemd` examples in this level were run on a real Linux VM. Memory-pressure and
    OOM-killer behaviour depends on the kernel's `overcommit` settings and available RAM, so exact numbers (how much
    memory before the kill, which process is chosen) will differ on your machine — the mechanism shown is real, the
    specific numbers are this lab's, and the lessons say so.

**Prerequisites:** Level 1 (processes, permissions, the filesystem). You do not need root for most of this level;
the lessons that do (LVM, OOM provocation) say so and suggest doing them in a disposable VM.

## Modules

1. **[Process States, Signals & Job Control](01-process-states-signals.md)**: running/sleeping/zombie/stopped,
   `SIGTERM` vs `SIGKILL` vs `SIGSTOP`, and why a zombie can't be killed.
2. **[Scheduling: Nice, Priorities & the CFS](02-scheduling-cfs.md)**: niceness vs real priority, how the Completely
   Fair Scheduler picks the next process to run.
3. **[Memory Management](03-memory-management.md)**: virtual address space, paging, page cache vs "free" memory, and
   provoking the OOM killer on purpose.
4. **[Disks & Block Devices](04-disks-lvm-filesystems.md)**: partitions, LVM physical/volume/logical groups, and
   creating an ext4 vs xfs filesystem.
5. **[Mounting, fstab & Network Filesystems](05-mounting-fstab-nfs.md)**: mount namespaces at a glance, `/etc/fstab`
   fields, bind mounts, and NFS basics.
6. **[systemd Deep Dive](06-systemd-deep-dive.md)**: units, targets, the dependency graph, and `systemd-analyze`.
7. **[Writing systemd Services & Timers](07-systemd-services-timers.md)**: a real unit file, `Restart=`, and a timer
   that replaces a cron job.
8. **[Logging & journald](08-journald-logging.md)**: structured logs, `journalctl` filters, and persistent vs
   volatile journals.
9. **[Device Files, udev & /dev](09-device-files-udev.md)**: character vs block devices, major/minor numbers, and
   how udev names a new device.
10. **[Project: Diagnose a Resource-Starved System](10-project-resource-diagnosis.md)**: a script that eats memory
    and CPU on purpose, and the diagnostic pass that finds and explains it.

## After Level 2

Level 3 goes outward: how Linux resolves a name and routes a packet, firewalls old and new, SSH's actual protocol,
SELinux/AppArmor, and the namespaces and cgroups that containers are built from.
