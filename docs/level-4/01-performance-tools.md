---
description: "Reading top, free, and iostat correctly on real output — including why load average isn't CPU percent and what iostat's %util actually measures."
---

# 01 · Performance Tools: top, vmstat, iostat & free Explained

Every one of these tools has been used once already somewhere earlier in this course — `free` in Level 2's
memory lesson, `vmstat` in Level 2's capstone, `ps`/`top`-style columns throughout Level 2. This lesson is where
they get read *correctly*, together, as the first few commands anyone reaches for on "something feels slow."

## Worked example: a real top snapshot and a real iostat run

```text
$ top -bn1 | head -n8
top - 16:32:36 up  6:14,  1 user,  load average: 0.02, 0.05, 0.02
Tasks: 146 total,   1 running, 144 sleeping,   0 stopped,   1 zombie
%Cpu(s):  1.9 us,  3.8 sy,  0.0 ni, 92.3 id,  1.9 wa,  0.0 hi,  0.0 si,  0.0 st
MiB Mem :   3896.5 total,   1018.4 free,    555.5 used,   2513.0 buff/cache
MiB Swap:      0.0 total,      0.0 free,      0.0 used.   3340.9 avail Mem

    PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND
 267517 vinodku+  20   0   10832   4672   2716 R   8.3   0.1   0:00.02 top

$ iostat -x 1 2 | tail -n5
Device    r/s   rkB/s rrqm/s %rrqm r_await rareq-sz   w/s    wkB/s ... %util
vda      0.87   44.66   0.45 34.25    0.20    51.59  4.76   224.31 ...  0.07
```

(Real output from this course's lab VM — and that `1 zombie` in the Tasks line is the same genuine leftover
`sshd` zombie process from Level 2, Lesson 1, still sitting there, caught again in the wild by a different tool.)
`top`'s `%Cpu(s)` line breaks CPU time into categories worth knowing individually: `us` (user-mode time, your
actual applications), `sy` (kernel/system-call time), `wa` (time spent waiting on I/O — CPU idle but not
"free," something's blocked on disk/network), and `id` (genuinely idle). `MiB Mem`'s split exactly mirrors Level
2's `free` lesson: `avail Mem` (3340.9) is far larger than plain `free` (1018.4) because of reclaimable
`buff/cache`, the same page-cache story from before, just in `top`'s own layout. `iostat -x`'s `%util` is the
single most misunderstood column here — explained below, because its intuitive reading ("percent of disk
capacity used") is wrong.

## How It Actually Works

**Load average** (Level 2's capstone project covered this in depth) is a smoothed, backward-looking average of
runnable-or-blocked-on-I/O processes — never read a single load average number as "current CPU load," always
pair it with `vmstat`'s immediate `r`/`us`/`sy`/`id` columns or `top`'s own `%Cpu(s)` line for the *right now*
picture.

`iostat -x`'s **`%util`** measures the percentage of the sampled time interval during which the device had **at
least one I/O request outstanding** — not "percentage of the disk's total bandwidth/IOPS capacity consumed." A
single-queue, low-concurrency workload can show `%util` near 100% while using only a small fraction of a fast
NVMe drive's actual throughput, simply because the device was *busy with something* almost continuously, one
request at a time, without ever being asked to do more work in parallel. Conversely, a device handling huge
sustained throughput with a very short average service time per request can show a surprisingly low `%util` if
requests complete quickly and leave gaps. This is specifically why `%util` must be read alongside `r_await`/
`w_await` (average time each read/write request took, in milliseconds) and `aqu-sz` (average queue depth) — high
`%util` *with* high `await` times is a real bottleneck; high `%util` with low `await` and low queue depth is
often just a single-threaded workload keeping one device continuously, if lightly, busy.

`top`'s `VIRT`/`RES`/`SHR` columns map directly onto Level 2's virtual-memory model: `VIRT` is the process's
entire virtual address space (often far larger than physical RAM in use, because it includes memory-mapped
libraries, reserved-but-unwritten pages, and more), `RES` is the resident set — pages actually backed by physical
RAM right now — and `SHR` is the portion of `RES` shared with other processes (commonly shared libraries, mapped
once in physical memory but counted toward every process that maps them) — which is exactly why summing every
process's `RES` column can overcount total memory use, since shared pages get counted once per process sharing
them.

## Common mistakes

- **Reading `%util` as "percent of disk capacity used" and sizing storage decisions on that number alone.** As
  explained above, it measures time-with-outstanding-I/O, not throughput headroom — always check `await` and
  `aqu-sz` alongside it before concluding a disk is actually saturated.
- **Summing `RES` across many processes to estimate "real" memory usage.** Shared libraries inflate this sum;
  `smem` or the `PSS` (proportional set size) metric from `/proc/<pid>/smaps_rollup` divides shared pages fairly
  across the processes using them, giving a materially more accurate total.
- **Treating `top`'s single live snapshot as representative of sustained behavior.** A one-second spike shows up
  identically to a genuine sustained problem in a single `top -bn1` capture — `vmstat 1 10` or a monitoring
  system's time-series view is what distinguishes a blip from a trend.

## Exercise

Run `top -bn1 | head -n8` and `iostat -x 1 3` on any Linux machine, and for the `iostat` output, identify one
device's `%util`, `r_await`/`w_await`, and `aqu-sz`. Based only on those three numbers (not `%util` alone), write
one sentence judging whether that device looks like a bottleneck right now, and explain your reasoning using the
model from this lesson.
