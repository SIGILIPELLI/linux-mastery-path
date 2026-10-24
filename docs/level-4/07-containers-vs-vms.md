---
description: "Where namespaces/cgroups-based isolation (containers) ends and real hardware virtualization (VMs) begins, measured with real timings from this course."
---

# 07 · Containers vs VMs: Where OS Fundamentals End and Virtualization Begins

Level 3 built a working, isolated, resource-limited process using nothing but `unshare` and a cgroup — the real
mechanism behind containers. This entire course was also written and verified inside a real virtual machine. Both
are "isolation," and the gap between them is the single most useful distinction in this whole level for deciding
which tool actually fits a given problem.

## The real, measured difference

```text
$ systemd-analyze   # this course's lab VM, full boot
Startup finished in 317ms (kernel) + 1.336s (initrd) + 2min 45.052s (userspace)
                                                        ^^^^^^^^^^^^^^^^^^^^^^^^
                                                        (mostly cloud-init network wait,
                                                        Level 1 Lesson 2 — but even without
                                                        that, a real kernel boot, firmware
                                                        init, and full userspace startup
                                                        are unavoidable real costs)

$ time sudo unshare --pid --mount-proc --fork true   # Level 3's namespace demo
real    0m0.013s
user    0m0.003s
sys     0m0.009s
```

A **container** (what `unshare`+cgroups built directly, Level 3 Lessons 7 and 10) is a normal process on the
**same running kernel**, made to see and consume only a restricted view of that kernel's resources. There is
exactly one kernel involved, one real boot already happened (long before the container existed), and creating a
new container is just creating a new process with some extra kernel bookkeeping (new namespaces, a cgroup
assignment) — which is why it completes in milliseconds, as measured directly above. A **virtual machine** boots
an entirely **separate kernel** on top of emulated or paravirtualized hardware, provided by a hypervisor (this
course's lab VM uses Apple's `vz` framework) — a genuinely separate operating system instance, with its own real
(if virtual) boot sequence, which is why even a fast VM boot measures in seconds to minutes, not milliseconds,
no matter how lightweight the guest OS is.

## How It Actually Works

This course's own Level 1 and Level 3 projects drew this exact line in practice, even if it wasn't named that
way at the time: `chroot` (Level 1) changed only the filesystem root view and shared literally everything else,
including the kernel, with the host — provably, since `uname -a` inside and outside the chroot reported the
identical kernel build. `unshare` (Level 3) added process-tree and hostname isolation on top of that same shared
kernel — still one kernel, more of it hidden from view. Neither of these ever involved a second kernel booting;
every layer of isolation this course built was isolation **within one running kernel instance**. A VM is
categorically different: the hypervisor presents virtual (or paravirtualized, like this lab's `virtio_blk` disk
from Level 4, Lesson 3) hardware to a guest kernel that boots independently, goes through its own BIOS/UEFI
handoff, its own `init`, its own process table that the host kernel knows nothing about directly — real isolation
at the hardware-emulation boundary, not at the single-kernel-resource-view boundary containers use.

This is exactly why a kernel vulnerability that lets code escape a container's namespace/cgroup boundary is
historically more common and more severe than one that escapes a VM's hypervisor boundary: a container escape
lands you directly in the **one shared kernel** everything was always running on, with no second security
boundary behind it; a VM escape (a "hypervisor breakout") has to defeat hardware-assisted virtualization
isolation specifically designed to resist exactly that, which is a substantially harder and rarer class of bug.
This isn't a reason to consider containers insecure by default — properly configured, with LSM profiles, seccomp,
and non-root user namespaces (all mentioned as missing from this course's own minimal demos), containers are
used safely at enormous scale — but it is the real, structural reason "a container is basically a lightweight VM"
undersells a genuine difference in what's actually providing the isolation.

## Common mistakes

- **Choosing a VM "to be safe" for a workload where container isolation (correctly configured, with the pieces
  this course's demos deliberately left out for simplicity) would be entirely sufficient**, paying real boot-time
  and resource overhead for a security margin the actual threat model may not need.
- **Choosing a container for a workload that genuinely needs a different kernel, different kernel-level
  security boundary, or hardware-level isolation** (multi-tenant untrusted code execution, for instance) **and
  discovering the shared-kernel assumption the hard way.**
- **Assuming "container" means one fixed thing.** As Level 3 showed directly, it's a *combination* of
  independently-tunable kernel mechanisms — a container with every available isolation feature enabled is a very
  different security posture from one with the bare minimum, even though both are correctly called "a container."

## Exercise

Time `unshare --pid --fork true` (or similar) against booting any VM you have access to, even one with a minimal
guest OS, and compare the two numbers directly, as this lesson did. Then explain, in your own words, using the
"what is actually providing the isolation" model from this lesson, why the two numbers differ by roughly two to
four orders of magnitude rather than by some small constant factor.
