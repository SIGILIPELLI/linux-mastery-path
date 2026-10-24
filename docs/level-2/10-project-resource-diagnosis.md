---
description: "Project: build a script that starves CPU on purpose, then diagnose it with ps, uptime and vmstat, reading the real numbers correctly."
---

# 10 · Project: Diagnose a Resource-Starved System

Every lesson in this level gave you one piece of the diagnostic toolkit — process state, scheduling, memory,
storage, `systemd`, logs, devices. This project puts the first three together: create a real CPU-starved system
on purpose, then diagnose it from the outside using exactly the tools and numbers you'd reach for on a real
incident, with nothing invented or simulated.

## Building the problem

```bash
cat > cpu_hog.sh << 'EOF'
#!/bin/bash
while true; do :; done
EOF
chmod +x cpu_hog.sh
./cpu_hog.sh &
./cpu_hog.sh &
```

This is deliberately the simplest possible CPU hog: an infinite loop doing nothing but checking its own condition
over and over, which the kernel schedules exactly like any other runnable, CPU-bound process (Lesson 2's CFS
model) — a pathological but completely realistic stand-in for "a process stuck in a bad loop" or "a worker that's
spinning instead of blocking on I/O," both real incident patterns.

## Diagnosing it with real output

```text
$ ps -eo pid,ppid,pcpu,pmem,stat,comm --sort=-pcpu | head -n6
    PID    PPID %CPU %MEM STAT COMMAND
 257439  257422  100  0.0 R    cpu_hog.sh
 257440  257422  100  0.0 R    cpu_hog.sh
   2057       1  0.3  0.8 Ssl  lima-guestagent
   9408    9371  0.2  0.9 Sl   containerd
      1       0  0.0  0.4 Ss   systemd

$ uptime
 16:22:38 up  6:04,  1 user,  load average: 0.00, 0.05, 0.04

$ vmstat 1 3
procs -----------memory---------- ---swap-- -----io---- -system-- -------cpu-------
 r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa st gu
 3  0      0 1044928  39724 2509912    0    0    59   202  266    0  0  0 99  0  0  0
 2  0      0 1045776  39724 2510048    0    0     0     0 2410  281 50  0 50  0  0  0
 2  0      0 1045836  39724 2510048    0    0     0     0 2212  105 50  0 50  0  0  0
```

(Real output from this course's lab VM, with two `cpu_hog.sh` processes genuinely running.) `ps --sort=-pcpu`
immediately names the two offenders: `STAT R` (runnable, actually on CPU or waiting for it — not sleeping) at a
flat `100` `%CPU` each, dwarfing every other process on the box. `uptime`'s **load average** — `0.00, 0.05, 0.04`
— is the one number here that's genuinely surprising if you expect it to reflect the hogs: these samples were
taken in the first couple of seconds after starting the loops, and load average is an *exponentially-decaying
moving average over 1/5/15 minutes*, so it takes real wall-clock time to climb and reflect a sudden CPU spike — a
system can be pegged at 100% CPU *right now* while `uptime` still shows a low number, purely because not enough
time has passed for the average to catch up. `vmstat`'s `r` column (processes runnable, not just running) jumping
to `2`–`3` on a VM with more cores available, alongside `us` (user-mode CPU%) sitting at `50` with `id` (idle) also
at `50`, is the real, immediate signal: roughly half this machine's CPU capacity is consumed by user-mode work that
never blocks, which `uptime`'s lagging average hadn't caught up to yet.

## How It Actually Works

The reason `ps`'s `%CPU` and `vmstat`'s `us`/`sy`/`id` percentages are trustworthy *immediately*, while `uptime`'s
load average is not, comes down to what each one actually measures. `ps` and `vmstat` report recent, short-window
CPU accounting pulled straight from `/proc` counters the kernel updates continuously — closer to an instantaneous
snapshot. Load average, by contrast, is explicitly defined as a smoothed, historical figure (the classic Unix
`CPU scheduler` load metric, counting both running *and* runnable-but-waiting processes, which on Linux also
counts processes blocked in uninterruptible I/O — `D` state from Lesson 1 of this level — which is why a
disk-bound system can show high load with *idle* CPU, a completely different root cause from this project's
CPU-bound example despite looking similar in a single `uptime` number). Reading load average correctly means
treating it as "how busy has this system been *recently*," not "how busy is it *right now*" — the two diverge
exactly in scenarios like this project's first few seconds.

## Common mistakes

- **Treating a single `uptime` reading as sufficient evidence a system is fine.** As this project shows directly,
  load average lags real CPU pressure by design; always cross-check with `vmstat`'s immediate `r`/`us`/`sy`/`id`
  columns or `ps --sort=-pcpu` before concluding "nothing's wrong."
- **Assuming high load average always means CPU contention.** Because Linux's load average also counts
  processes in uninterruptible I/O wait (`D` state), a load spike with low CPU usage and high `wa` (I/O wait) in
  `vmstat` points at disk or network storage, not the CPU scheduler — a materially different fix.
- **Killing the first high-`%CPU` process you see without checking `STAT`.** A process at high `%CPU` in `R`
  state doing real, intended work (a legitimate batch job) looks identical in that one column to a runaway loop —
  `ps`'s longer history (`etime`, `time`) and whether the workload is expected are what actually distinguish them.

## Exercise

Reproduce this project's CPU hog yourself (two infinite-loop background processes), then within the first 5
seconds run `uptime`, `vmstat 1 3`, and `ps --sort=-pcpu`. Confirm for yourself that load average hasn't caught up
yet while the other two already show the real picture. Then let the hogs keep running for at least a full minute
and re-check `uptime` — watch the 1-minute figure finally climb to reflect what the other tools showed you
immediately.
