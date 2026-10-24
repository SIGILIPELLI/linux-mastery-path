---
description: "Linux Level 4: performance tools, strace/ltrace/perf, I/O scheduling, kernel modules, /proc & /sys debugging, boot recovery, and a capstone server build."
---

# Level 4 · Performance, Troubleshooting & Capstone

Level 4 is what you reach for when something is wrong and you don't yet know what: the performance tools that tell
you where time is going, the tracers that show you every syscall a process makes, the kernel module system, and
the boot-recovery skills for when the system won't even start. It ends with a capstone that builds a server, breaks
it on purpose, and gets it back.

!!! note "What was run, and what wasn't"
    `top`, `vmstat`, `iostat`, `free`, `strace`, `perf` (where the kernel/VM supported perf events), module
    `insmod`/`lsmod` commands, and the boot-recovery steps were run on a real Linux VM. Distro comparisons in module
    8 and kernel release/LTS details in module 9 are documentation-based (you can't "run" a comparison of five
    distributions) and are dated to October 2026; check current LTS status before relying on it long-term.

**Prerequisites:** Levels 1–3. The capstone assumes you're comfortable combining filesystem, process, systemd,
network and security content from every earlier level.

## Modules

1. **[Performance Tools](01-performance-tools.md)**: `top`/`htop`, `vmstat`, `iostat`, `free`, and reading load
   average correctly (it's not CPU percent).
2. **[Tracing & Profiling](02-strace-ltrace-perf.md)**: `strace` for syscalls, `ltrace` for library calls, and
   `perf` for sampling where CPU time actually goes.
3. **[Filesystem Performance & I/O Scheduling](03-filesystem-performance-io.md)**: I/O schedulers, `iostat` queue
   depth, and why a "slow disk" is sometimes a slow filesystem choice.
4. **[Kernel Modules](04-kernel-modules.md)**: loading, unloading, and building a trivial "Hello, kernel" module.
5. **[/proc and /sys as Debugging Tools](05-proc-sys-debugging.md)**: reading a hung process's state, open files
   and memory map without a debugger.
6. **[Troubleshooting Boot Failures & Recovery Mode](06-boot-failure-recovery.md)**: single-user/rescue targets,
   a broken `fstab`, and recovering from it.
7. **[Containers vs VMs](07-containers-vs-vms.md)**: where the namespaces/cgroups from Level 3 end and a hypervisor
   begins.
8. **[Linux Distros Compared](08-distros-compared.md)**: Debian/Ubuntu, RHEL/Fedora, Arch and Alpine — init systems,
   package managers and release models.
9. **[Kernel Versions, LTS & Staying Current](09-kernel-versions-lts.md)**: the mainline/stable/LTS split and how
   to tell which one you're running.
10. **[Capstone: Build, Harden & Diagnose a Linux Server From Scratch](10-capstone-server-build.md)**: provision a
    VM, apply Level 1–3 hardening, then diagnose three injected faults.
