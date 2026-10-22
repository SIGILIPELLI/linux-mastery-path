---
description: "How Linux shares CPUs: run queues, nice, context switches, what load average counts, CPU states, with a macOS nice and load experiment."
---

# 04 · CPU Scheduling & Load Average

"The load is 12" means nothing until you know how many CPUs there are, what the load counts, and whether the work is CPU-bound or waiting on I/O. This lesson explains how the scheduler divides CPU time and how to read `uptime`, `top` and `vmstat` without being misled.

!!! note "What was run"
    The scheduler and `/proc/loadavg` are Linux-specific and **were not run**; they come from `proc_loadavg(5)` (man7.org) and the kernel scheduler documentation (docs.kernel.org, read October 2026). I ran one experiment on **macOS** (8 CPUs): 16 busy processes, half at nice 0 and half at nice 15, while sampling load average. The
    results are macOS results, and they differ from what Linux's scheduler is documented to do, which I point out. See Level 1 · Lesson 01.

## The scheduler's job

At any instant each CPU runs at most one thread. A thread is either **running**, **runnable** (ready, waiting for a CPU, in a run queue), or **sleeping** (waiting for I/O, a timer, a lock). The scheduler picks which runnable thread gets each CPU next, for how long, and tries to keep a thread on the same CPU
(to preserve its cache). Switching from one thread to another is a **context switch** (save registers, switch address space); useful, but not free, and a system with huge numbers of switches per second spends real time just switching.

Linux's general-purpose scheduler was the **Completely Fair Scheduler (CFS)** from 2.6.23; the kernel documentation says it is now "making room for EEVDF", its successor. CFS models an "ideal, precise multi-tasking CPU" that runs every runnable task simultaneously at 1/N speed; since real CPUs run one task at a time, it tracks each task's **virtual
runtime** and always picks the task that has had the least. The details of the algorithm have changed between kernel versions, but the user-visible contract is stable: runnable tasks share CPU in proportion to their **weight**, and sleeping tasks wake with a preference so interactive tasks feel responsive.

Scheduling **policies**: `SCHED_OTHER`/normal for ordinary tasks; `SCHED_BATCH` and `SCHED_IDLE` for background work; real-time `SCHED_FIFO` and `SCHED_RR` that preempt normal tasks (dangerous: a spinning real-time task can starve the system); `SCHED_DEADLINE` for periodic jobs with deadlines. Inspect and change them with `chrt`.

## nice and priorities

`nice -n 10 cmd` and `renice` change a normal task's weight: higher nice means lower weight and a smaller CPU share *when CPUs are contended*; if the CPU is idle, a nice 19 task still gets 100%. Nice only matters under contention. The kernel's weight table makes each nice step an exponential change (the exact
values are in the kernel source, which I did not check), so nice 19 is dramatically weaker than nice 0. Linux also has I/O priorities (`ionice`) and cgroup CPU controls (`cpu.weight`, `cpu.max`, Lesson 06), which are the production tools for fairness because they act on services, not single processes.

### What I measured on macOS

I started 16 CPU-spinning processes on an 8-CPU Mac, 8 at nice 0 and 8 at nice 15 (Python `os.nice`), and measured each one's CPU seconds over a 3-second window:

```text
nice  0: mean CPU seconds in 3s window = 1.38 ; mean loop iterations = 1.79e+07
nice 15: mean CPU seconds in 3s window = 1.38 ; mean loop iterations = 1.81e+07
```

**No difference.** Both groups got an equal share: with 16 runnable threads on 8 CPUs, an even split is 1.5 s of CPU each in 3 s, close to the 1.38 s measured. On macOS, nice values had no measurable effect on this workload (Apple's scheduler uses different mechanisms and heterogeneous performance/efficiency cores).
So: **don't carry assumptions across operating systems**. On Linux, the CFS/EEVDF weighting is documented to favour the nice 0 group strongly under contention, but I did not measure it here.

## Load average

`uptime` prints three numbers: the average "load" over the last 1, 5 and 15 minutes. Per `proc_loadavg(5)`, they are "the number of jobs in the run queue (state R) or waiting for disk I/O (state D)" averaged over those windows. Two important consequences:

1. **Linux load counts uninterruptible (D state) tasks.** A machine with idle CPUs can show a load of 50 because 50 processes are stuck in disk or NFS waits. (My understanding is that BSD-derived systems such as macOS historically count only runnable threads; I did not verify that.) So on Linux, high load with low CPU means *I/O* trouble; high load with high CPU means CPU saturation.
2. **Interpret load relative to the CPU count.** On 8 CPUs, a load of 8 is fully busy, 4 is half busy, 16 means about one waiting task per CPU. Rules of thumb: sustained load above the CPU count means queueing; a 1-minute value rising above the 15-minute one means it's getting worse.

My macOS measurement: the 1-minute load average read 3.82 before and 5.67 during the 16-thread test (on 8 CPUs) — a lagging exponentially damped average, so it moves slowly toward the instantaneous count of 16 (it can't catch up in a 3-second test). That damping is why load average is a trend, not a gauge.

### Where the time goes: CPU states

`top`/`vmstat`/`mpstat` break CPU time into states, from `/proc/stat` (Lesson 03):

| State | Meaning |
|---|---|
| `us` user | Application code |
| `sy` system | Kernel code on behalf of processes (system calls, network stack) |
| `ni` | Niced user code |
| `id` idle | Nothing to run |
| `wa` iowait | Idle **while a task waits for I/O** (the CPU could run something else; high `wa` signals I/O-bound work, not a busy CPU) |
| `hi`/`si` | Hardware / software interrupt handling (network-heavy hosts show high `si`) |
| `st` steal | Time a **virtual machine** wanted a CPU but the hypervisor ran something else; high `st` means noisy neighbours or an overcommitted host |

Reading patterns: high `us` plus load ≈ CPU count → add CPU or optimise code; high `sy` → many syscalls/network packets; high `wa` plus D-state load → storage; high `st` → talk to your cloud provider or resize. Per-core view matters: a single-threaded program can saturate one core (one core at 100%, the box "12% busy") and no amount of other CPUs helps (`mpstat -P ALL 1`, `top` then `1`).

## A CPU triage routine (not run)

```bash
uptime                       # load vs CPU count (nproc)
mpstat -P ALL 1 3            # per-core us/sy/wa/steal
top -H -p <pid>              # per-thread CPU of one process
pidstat -u -w 1 5            # per-process CPU and context switches (voluntary = waited; involuntary = preempted)
perf top / perf record -g -p <pid>   # which functions burn CPU (Lesson 09)
```

Context switch counts in `/proc/<pid>/status` (`voluntary_ctxt_switches`, `nonvoluntary_ctxt_switches`): many **involuntary** switches mean the task is being preempted (CPU contention); many **voluntary** ones mean it blocks often (I/O or locks).

## How It Actually Works

Each CPU has its own run queue of runnable tasks, ordered by virtual runtime (a red-black tree in CFS). A timer interrupt (the scheduler tick), plus wake-up events, trigger a decision: if another task is owed more CPU than the current one, the kernel preempts. A **load balancer** periodically migrates tasks between run queues to even out load, taking cache
and NUMA locality into account. When a task blocks (read from disk), it leaves the run queue and the CPU picks another; when the I/O completes, an interrupt makes the task runnable again, often with a wake-up bonus. The load average is maintained by a periodic job that samples `nr_running + nr_uninterruptible` every five seconds
and folds it into three exponentially decaying averages, which is exactly why it lags and why D-state tasks count.

## Common mistakes

- **Reading load without the CPU count.**
- **Assuming high load means high CPU** (on Linux, check `wa` and D-state tasks).
- **Ignoring steal time** on VMs.
- **Treating `nice` as a service-level control** (use cgroup CPU weights and limits).
- **Averaging across cores** and missing a single saturated core.
- **Real-time priorities** for ordinary services.
- **Porting expectations between macOS and Linux**, as my own experiment showed.

## Exercise

1. On a Linux VM with 4 CPUs, run 8 busy loops (4 at nice 0, 4 at nice 15) for 30 seconds, measure each group's CPU time with `ps -o pid,ni,time`, and compare with my macOS result.
2. Create high load with low CPU use: start 20 processes that read from a slow NFS mount or `dd` from a throttled device; confirm with `uptime` and `vmstat` that load is high and `wa` is high.
3. Use `pidstat -w` to find a process with many involuntary context switches and explain what it means.
4. Given load averages 20.1 / 8.4 / 3.0 on a 16-CPU host, explain what's happening and what you would check first.
