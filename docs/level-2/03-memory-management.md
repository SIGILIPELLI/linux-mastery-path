---
description: "Virtual memory, paging, the page cache, and a real, deliberately-triggered OOM kill inside a memory-limited cgroup scope."
---

# 03 · Memory Management: Virtual Memory, Paging & the OOM Killer

`free -h`'s "free" column being tiny while "available" stays large confuses nearly everyone the first time they
look closely, and "why did the OOM killer pick *that* process" is one of the most common real incident-review
questions on any team running Linux in production. Both come from the same underlying model: virtual memory,
the page cache, and what the kernel does when physical memory genuinely runs out.

## Virtual memory, in one paragraph

Every process sees its own private **virtual address space** — a process's pointers are addresses in that private
space, not physical RAM addresses. The kernel's page tables map chunks of that virtual space (**pages**, 4 KiB on
most Linux systems) to physical memory pages, translated by the CPU's memory-management unit on every access. This
indirection is what makes multiple processes safely share one machine without being able to read each other's
memory by accident, what makes `fork()`'s copy-on-write trick (Lesson 7, Level 1) possible, and what lets the
kernel page infrequently-used memory out to swap (if configured) without any program needing to know.

## Worked example: a real, deliberate, cgroup-scoped OOM kill

```text
$ free -h
               total        used        free      shared  buff/cache   available
Mem:           3.8Gi       552Mi       1.0Gi       1.1Mi       2.5Gi       3.3Gi
Swap:             0B          0B          0B

$ sudo systemd-run --scope -p MemoryMax=100M --unit=memtest python3 /tmp/eatmem.py
Running as unit: memtest.scope; invocation ID: 71182bc0a74847d699c6e9d720e28170
allocated 10 MB
allocated 60 MB
(scope terminated)

$ sudo dmesg | tail -n4
[21467.552821] python3 invoked oom-killer: gfp_mask=0xcc0(GFP_KERNEL), order=0, oom_score_adj=0
[21467.556631]  oom_kill_process+0x2a4/0x350
[21467.558380] oom-kill:constraint=CONSTRAINT_MEMCG,...,task_memcg=/system.slice/memtest.scope,task=python3,pid=246692,uid=0
[21467.558406] Memory cgroup out of memory: Killed process 246692 (python3) total-vm:121648kB, anon-rss:102100kB, file-rss:6084kB, shmem-rss:0kB, UID:0 pgtables:272kB oom_score_adj:0
```

(Real output from this course's lab VM — this is a genuine OOM kill, not a simulated log line.) `free -h` on this
VM shows **3.8 GiB total but no swap configured at all**, which is itself common on cloud VMs and containers.
`systemd-run --scope -p MemoryMax=100M` runs the Python script inside a fresh **cgroup** (Level 3 covers cgroups
properly) capped at 100 MB — the script logs successful allocations up to 60 MB and then simply stops, because
somewhere past that point it crossed the 100 MB limit and was killed outright, with no `MemoryError` exception ever
reached in Python (`SIGKILL` doesn't give a process a chance to catch anything). `dmesg` shows the kernel's own
account: `constraint=CONSTRAINT_MEMCG` says explicitly this was a **cgroup-level** OOM kill, scoped to
`memtest.scope`, not a whole-system OOM event — and this distinction matters in practice: on a modern
`systemd`-managed Linux system, almost every "OOM killed my process" incident you'll actually investigate is this
cgroup-scoped kind, because `systemd` puts every service in its own cgroup and most services set (or inherit) a
memory limit, rather than the rarer, more dramatic system-wide OOM kill that happens when the *entire machine*
runs out of memory.

## How It Actually Works

The gap between `free`'s "free" and "available" columns is the **page cache**: the kernel keeps recently-read file
data cached in RAM (shown in `buff/cache`) because reusing cached pages is far faster than re-reading from disk.
Critically, this cached memory **is not wasted** and **is not unavailable** — it's reclaimable on demand the moment
something actually needs it, which is exactly what `available` reports: free memory *plus* cache the kernel could
drop immediately without hurting anything. A system reporting tiny "free" and large "available" is behaving
completely normally; a system where *both* are small is the one actually worth worrying about.

The **OOM killer** is the kernel's response when it genuinely cannot satisfy a memory request — not when memory
usage is merely high, but when reclaiming cache, compacting memory, and (if configured) swapping still aren't
enough. Rather than letting the whole system deadlock or crash, it picks a process to sacrifice using a computed
**oom_score** (readable per-process at `/proc/<pid>/oom_score`) that weighs memory usage heavily, and can be
nudged with `/proc/<pid>/oom_score_adj` (a critical system service might set this very negative to make itself a
last resort; a known-disposable batch job might set it positive to volunteer first). Since Linux 4.19, the kernel
ships `oomd`-style **PSI** (Pressure Stall Information, in `/proc/pressure/`) that lets userspace intervene
*before* the kernel OOM killer has to act at all — reclaiming memory, pausing or killing lower-priority cgroups
proactively — which is increasingly how systems avoid the kernel OOM killer's necessarily blunt, late,
last-resort decision in the first place.

## Common mistakes

- **Reading `free`'s "free" column as "how much memory do I have left."** It almost always understates real
  headroom, because it doesn't credit reclaimable cache — "available" is the number that answers that question.
- **Assuming the OOM killer always targets the process that's "obviously" using the most memory.** The score also
  factors in `oom_score_adj` and some kernel heuristics around a process's own children — a cgroup-scoped kill, as
  shown above, can also take out a process that's well within the *system's* overall memory budget but has
  exceeded its own cgroup's specific limit, which is a completely different trigger from whole-system pressure.
- **Treating "no swap configured" as automatically bad or automatically fine.** No swap means memory pressure turns
  into OOM kills faster (less room to relieve pressure), which is sometimes a deliberate choice (predictable
  latency, no swap thrashing) and sometimes an oversight — know which one is true for your system.

## Exercise

Run `free -h` and explain, in your own words, why `available` is larger than `free` on your system right now using
the page-cache model from this lesson. Then — **only inside a disposable VM or container, never on a machine you
care about** — reproduce a scoped OOM kill with `systemd-run --scope -p MemoryMax=50M -- python3 -c
"[bytearray(10_000_000) for _ in range(100)]"` and find the resulting kill in `dmesg`; identify whether `dmesg`
reports `CONSTRAINT_MEMCG` (cgroup-scoped, like this lesson's example) or a whole-system constraint, and explain
the difference.
