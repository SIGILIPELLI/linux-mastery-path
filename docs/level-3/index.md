---
description: "Linux Level 3: system calls, memory, /proc, scheduling, I/O, namespaces and cgroups, capabilities, the network stack and a /proc monitor."
---

# Level 3 · Internals & Performance

Level 3 explains why Linux behaves the way it does: the user/kernel boundary, lazy memory allocation and the OOM killer, the kernel's file-based windows (`/proc`, `/sys`), how the scheduler shares CPUs and what load average counts, the page cache and the I/O path, how namespaces and cgroups build containers, how capabilities and mandatory access control shrink root, how a TCP listener queues connections, and a method for performance analysis. It
ends with a `/proc` monitor tested against fabricated `/proc` trees.

!!! note "What was run, and what wasn't"
    This level is the most Linux-specific, and **no Linux kernel interface (`/proc`, cgroups, namespaces, `perf`, `strace`) was available**, so none were run. Linux facts come from the man pages (man7.org) and kernel documentation (docs.kernel.org), October 2026. What was run on macOS: system-call and `fork` timings, a lazy `mmap` allocation, a nice and load experiment (whose result differed from Linux's documented behaviour, and the
    lesson says so), a listen-backlog test, an I/O experiment that was inconclusive in one part and says so, plus **parsers and monitors tested on hand-built fixtures** in the documented formats. One lesson also records a mistake I made (a calculation written before running the code) and how it was corrected.

**Prerequisites:** Levels 1 and 2.

## Modules

1. **[System Calls & the Kernel Boundary](01-syscalls-kernel.md)**: strace, errno, lazy allocation, copy-on-write `fork`.
2. **[Memory: Page Cache, Swap & the OOM Killer](02-memory-management.md)**: `MemAvailable`, overcommit, who gets killed.
3. **[/proc and /sys](03-proc-sys.md)**: formats, deltas vs gauges, a fixture-tested parser.
4. **[CPU Scheduling & Load Average](04-cpu-scheduling-load.md)**: what load counts (including D state), `nice`, steal.
5. **[I/O, the Block Layer & Storage Performance](05-io-storage-performance.md)**: write-back, `fsync`, reading `iostat`.
6. **[Namespaces & cgroups](06-namespaces-cgroups.md)**: how containers work; cgroup v2 files.
7. **[Capabilities, SELinux & AppArmor](07-mac-capabilities.md)**: a tested capability-mask decoder.
8. **[The Network Stack](08-network-stack.md)**: SYN and accept queues, TIME_WAIT, keepalives, netfilter.
9. **[Performance Analysis: The USE Method](09-performance-method.md)**: a vmstat triage function.
10. **[Project: A /proc-Based Monitor](10-project-proc-monitor.md)**: parameterised proc root, 8 tests.

## After Level 3

Level 4 is operations: robust scripts, backups that restore, configuration management, troubleshooting methodology, patching, disk and network fault diagnosis, auditing, containers and a runbook capstone.
