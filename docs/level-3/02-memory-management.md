---
description: "Linux memory: page cache, MemAvailable vs MemFree, swap and swappiness, overcommit modes and how the OOM killer picks a victim."
---

# 02 · Memory: Page Cache, Swap & the OOM Killer

"Free memory" is the most misread number on a Linux server. A healthy machine will show almost no *free* memory, because the kernel uses spare RAM to cache files, and that's a feature. The real questions are: **how much memory can applications still get? Is the system swapping under pressure? Who gets
killed when it runs out?**

!!! note "What was run"
    Linux memory interfaces (`/proc/meminfo`, `free`, `vmstat`, `dmesg`, sysctls) were **not run** (no Linux machine). Field meanings and defaults are from `proc_meminfo(5)` and the kernel's `vm.rst` sysctl documentation (man7.org and docs.kernel.org, October 2026). The one run-on-macOS experiment (lazy allocation via `mmap`) is in
    Lesson 01. See Level 1 · Lesson 01.

## Virtual memory in one picture

Each process sees its own **virtual address space**. The kernel maps virtual pages to physical RAM on demand (a *page fault* on first touch; Lesson 01 showed that mapping 512 MiB changed nothing until pages were touched). Useful sizes for one process:

| Metric | Meaning |
|---|---|
| **VSZ / VIRT** | Total virtual address space mapped (can be huge and harmless) |
| **RSS / RES** | Pages currently resident in RAM (includes shared library pages) |
| **PSS** | RSS with shared pages divided among the processes sharing them: the fairest per-process number (`/proc/<pid>/smaps_rollup`) |
| **Shared / private** | Pages used by several processes (libraries) vs by one |

Summing RSS across processes over-counts shared pages; use PSS or system-level numbers.

## System-level memory: read the right line

`free -h` on a Linux box shows something like (illustrative values, not from a real machine):

```text
              total   used   free  shared  buff/cache  available
Mem:           16Gi   3.1Gi  0.4Gi   0.2Gi     12Gi        12Gi
Swap:          2Gi     0B    2Gi
```

- **free** (`MemFree`) is memory that is entirely unused. It's normally small.
- **buff/cache** is the **page cache** (file data cached from disk, `Cached`) plus block buffers and reclaimable slab. The kernel gives this back instantly when applications need memory (clean pages simply get dropped).
- **available** (`MemAvailable`, since Linux 3.14) is the kernel's *estimate of how much memory is available for starting new applications without swapping*, per `proc_meminfo(5)`. **This is the number to monitor**, not `free`.

So in this illustration a "full" 16 GiB machine has 12 GiB available. Alerting on "free < 10%" produces constant false alarms; alert on low `MemAvailable`, sustained swap-in activity, and OOM-kill events. Running `echo 3 > /proc/sys/vm/drop_caches` to "free memory" just throws away useful cache and makes the machine slower
until it refills.

## Swap

Swap is disk space used to hold **anonymous memory pages** (heap, stack: pages with no file to be re-read from) when RAM is tight, so the kernel can use the RAM for something more valuable, such as cache. It is not just an emergency measure: a little swap lets the kernel move truly idle pages out. But
heavy swapping (**thrashing**) makes everything crawl. Watch `vmstat 1` columns `si`/`so` (swap in/out per second): sustained non-zero values mean memory pressure.

`vm.swappiness` (per kernel docs: a value from 0 to 200, **default 60**) expresses the relative I/O cost of swapping versus evicting page cache; at 100 the kernel treats them as equally costly, lower values favour keeping anonymous pages in RAM. Databases often use a lower value. Swap on SSD or zram changes the trade-off.
Don't copy `swappiness=1` folklore; measure under your workload.

## Overcommit

Because allocation is lazy, the kernel can promise more virtual memory than exists. `vm.overcommit_memory` (documented in the kernel sysctl docs):

| Value | Policy |
|---|---|
| **0** (default) | Heuristic: refuse *obvious* overcommits (a request larger than total memory plus swap) |
| **1** | Always allow; "pretend there is always enough memory until it actually runs out" |
| **2** | Never overcommit beyond swap plus `overcommit_ratio`% of RAM (or `overcommit_kbytes`) |

Mode 0 works because many programs `malloc` huge buffers "just in case" and touch little of it, as the kernel documentation notes. The cost: the failure comes **late**, when pages are touched, as an OOM kill rather than as a failed `malloc` the program could handle.

## The OOM killer

When the kernel cannot reclaim enough memory to satisfy an allocation, it invokes the **OOM killer**, which chooses a process, scores each by memory use (and an adjustable factor) and kills it with SIGKILL. By default (`vm.oom_kill_allocating_task = 0`, per the docs) it scans the task list and picks the process that frees the most memory,
usually the biggest hog, which is not necessarily the one that caused the pressure (the victim can be your database while a leaky batch job is to blame).

You'll find it in the kernel log:

```text
Out of memory: Killed process 4242 (java) total-vm:... anon-rss:... file-rss:... shmem-rss:... oom_score_adj:0
```

(`journalctl -k | grep -i "out of memory"` or `dmesg -T`; the hand-written fixture line in Level 2 · Lesson 03 mimics this.) A process killed by SIGKILL exits with status 137 (Level 1 · 07), so a container or service that "just died with 137" is a prime OOM suspect.

Tuning knobs: `/proc/<pid>/oom_score_adj` (-1000 to 1000; -1000 exempts a process, which is dangerous if it leaks), systemd's `OOMScoreAdjust=` and `MemoryMax=` (a cgroup limit: exceeding it triggers an OOM kill *within that cgroup* only; Lesson 06), and userspace killers such as `systemd-oomd` or `earlyoom` that act before
the machine thrashes. In containers, the **cgroup memory limit** makes the kernel kill your process even though the host has plenty of free RAM, the single most common "mysterious restarts" cause on Kubernetes.

## Other memory consumers

- **Slab** (kernel objects: dentry and inode caches), shown in `/proc/meminfo` as `Slab`, `SReclaimable`; a huge dentry cache after scanning millions of files is normal and reclaimable.
- **Shared memory / tmpfs** (`/dev/shm`, `/tmp` if tmpfs): counts as memory, not disk (Lesson 04's `tmpfs`), and isn't released while files exist.
- **Huge pages** (transparent or explicit): fewer page-table entries and TLB misses, but they can cause memory bloat or latency stalls for some databases (their docs often say to disable THP).
- **Dirty pages**: written data not yet flushed to disk (`Dirty`, `Writeback`); too many stalls writers (Lesson 05).

## A memory triage routine (not run)

```bash
free -h                         # available? swap used?
vmstat 1 5                      # si/so (swap), b (blocked), wa (I/O wait)
ps aux --sort=-rss | head       # biggest by RSS (remember shared pages)
cat /proc/meminfo | egrep "MemAvailable|SwapFree|Dirty|Slab"
journalctl -k | grep -i -E "out of memory|oom"
systemctl status <unit> ; systemd-cgtop    # cgroup memory use per service
```

## How It Actually Works

The kernel divides RAM into pages and tracks them on LRU lists (active and inactive, for file-backed and anonymous pages). When free pages drop below a watermark, the **kswapd** thread reclaims: it drops clean file pages first, writes dirty ones back, and swaps out cold anonymous pages as `swappiness` directs. If
allocation still fails ("direct reclaim" in the allocating process stalls it), the OOM killer is the last resort. `MemAvailable` is computed from free pages plus the parts of the page cache and slab that can be reclaimed without hurting, which is why it predicts allocation headroom better than `MemFree`. With cgroups (Lesson 06) the same accounting
and reclaim happen per group with their own limits, which is how one runaway container is killed without taking down the host.

## Common mistakes

- **Alerting on "free memory"** instead of `MemAvailable` and pressure signals.
- **Dropping caches** as a fix.
- **Sizing from VSZ** or summing RSS.
- **No swap at all** on a general server, or swap on a slow disk with high swappiness, depending on workload; know why.
- **Blaming the victim**: the process OOM-killed isn't always the leaker.
- **Setting `oom_score_adj=-1000`** on a leaking service.
- **Forgetting container cgroup limits** when diagnosing restarts.
- **`overcommit_memory=1`** without understanding that failures become kills.

## Exercise

1. On a Linux VM, run a program that allocates and touches 1 GiB while watching `free -h`, `vmstat 1` and `dmesg -w`; then set a cgroup `MemoryMax=500M` (Lesson 06) and observe the OOM kill inside the cgroup.
2. Compute `MemAvailable` from `/proc/meminfo` by hand (free + reclaimable cache) and compare with the reported value; note the difference.
3. Write an alert rule (in words) for memory that avoids the `free` trap and fires only on sustained pressure.
4. Explain why `malloc` in a program under `overcommit_memory=0` can succeed and the process still die later.
