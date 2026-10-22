---
description: "Performance analysis with the USE method: the first-minute checklist, profiling with perf, and a vmstat triage function tested on fixtures."
---

# 09 · Performance Analysis: The USE Method & Tools

When a server is "slow", the temptation is to run `top`, see something big, and fix it. That finds the loudest thing, not necessarily the bottleneck. A method keeps you honest: check each **resource** systematically for **U**tilization, **S**aturation and **E**rrors (the USE method, popularised by Brendan Gregg), find the bottleneck, then drill into
the software responsible.

!!! note "What was run"
    The Linux performance tools named here (`vmstat`, `iostat`, `mpstat`, `sar`, `perf`, `bpftrace`) are Linux-only and **were not run**. Their output formats come from their documentation; the numbers in the triage fixtures below are **invented by me** in the documented `vmstat` layout to exercise the analysis code. The triage function and its 6 pytest tests were run on macOS. The
    thresholds are rules of thumb, not standards. See Level 1 · Lesson 01.

## USE: three questions per resource

| Resource | Utilization (how busy) | Saturation (queued work) | Errors |
|---|---|---|---|
| **CPU** | `mpstat` us+sy, per core | Run queue length (`vmstat r` above CPU count), load average (Lesson 04), `cpu.stat` throttling | Machine-check/ECC events in `dmesg` |
| **Memory** | `free`, `MemAvailable` | Swapping (`vmstat si/so`), page-scan activity, OOM kills (Lesson 02) | OOM messages, allocation failures |
| **Disk** | `iostat %util` (careful on SSD) | `aqu-sz`, `await`, blocked processes (`vmstat b`) (Lesson 05) | `dmesg` I/O errors, SMART |
| **Network** | `sar -n DEV`, bandwidth vs link speed | Socket queues (`ss Recv-Q/Send-Q`), listen overflows, retransmits (Lesson 08) | Drops/errors in `ip -s link`, `nstat` |
| **File descriptors, threads, locks** | `/proc/sys/fs/file-nr`, `ulimit` use | Waiters on a lock (`futex`), thread-pool queue | `EMFILE`, `ENOMEM` |

Saturation and errors are what tell you a resource is the bottleneck; utilization alone misleads (a 100% busy CPU with an empty run queue is fine; a 60% busy disk with a long queue is not).

## The first sixty seconds (Linux; not run)

```bash
uptime                 # load averages: trending up or down?
dmesg -T | tail        # OOM kills, hardware errors, filesystem errors
vmstat 1 5             # r, b, si/so, us/sy/id/wa/st, cs
mpstat -P ALL 1 3      # per-CPU balance: one hot core?
pidstat 1 3            # which processes use CPU
iostat -xz 1 3         # disk await/aqu-sz/util
free -m                # available memory
sar -n DEV 1 3         # network throughput; sar -n TCP,ETCP 1 3 for retransmits
ss -s ; top            # socket summary; overview
```

Ten commands, one minute: the resource that stands out on saturation or errors is where to dig. Record the output (or `sar` history) so you can compare against normal.

### Automating the first read: a vmstat triage (run on fixtures)

`vmstat`'s first line is an average **since boot**, so the code skips it, then applies rules of thumb.

```python
"""Triage a Linux `vmstat` sample using the USE method (Utilization, Saturation, Errors). Fixture-driven; thresholds are rules of thumb."""
COLS = "r b swpd free buff cache si so bi bo in cs us sy id wa st".split()

def parse(text):
    rows = []
    for line in text.strip().splitlines():
        f = line.split()
        if not f or not f[0].isdigit(): continue                      # skip the two header lines
        if len(f) != len(COLS): raise ValueError(f"expected {len(COLS)} columns, got {len(f)}")
        rows.append(dict(zip(COLS, map(int, f))))
    return rows

def triage(rows, ncpu):
    steady = rows[1:] if len(rows) > 1 else rows                     # the first vmstat line is an average since boot
    avg = lambda k: sum(r[k] for r in steady) / len(steady)
    out = []
    if avg("r") > ncpu: out.append(f"CPU saturation: run queue {avg('r'):.1f} > {ncpu} CPUs")
    if avg("us") + avg("sy") > 85: out.append(f"CPU utilization {avg('us') + avg('sy'):.0f}% (us+sy)")
    if avg("wa") > 20: out.append(f"I/O wait {avg('wa'):.0f}%: tasks blocked on storage")
    if avg("st") > 5: out.append(f"CPU steal {avg('st'):.0f}%: the hypervisor is taking CPU")
    if avg("si") + avg("so") > 0: out.append(f"swapping: si={avg('si'):.0f} so={avg('so'):.0f} KB/s: memory pressure")
    if avg("b") > 0: out.append(f"{avg('b'):.1f} tasks blocked in uninterruptible sleep on average")
    if avg("cs") > 50000: out.append(f"{avg('cs'):.0f} context switches/s: check lock contention / thread count")
    return out or ["no obvious saturation in this sample"]
```

Results on four invented 2 to 3 sample fixtures (a 4-CPU host):

```text
HEALTHY   -> ['no obvious saturation in this sample']
CPU_BOUND -> ['CPU saturation: run queue 13.0 > 4 CPUs', 'CPU utilization 98% (us+sy)']
IO_BOUND  -> ['I/O wait 72%: tasks blocked on storage', '15.0 tasks blocked in uninterruptible sleep on average']
SWAPPING  -> ['I/O wait 40%: tasks blocked on storage', 'swapping: si=8000 so=6000 KB/s: memory pressure', '2.0 tasks blocked in uninterruptible sleep on average']
```

Note the I/O-bound fixture does **not** raise "CPU saturation" even though the machine is slow, matching the lesson that high load with low CPU use points to storage (Lesson 04), and the swapping fixture also shows I/O wait, because swap traffic is disk traffic: symptoms interact. The pytest suite (6 tests) checks each
scenario and that the first line is ignored. In writing the swapping fixture's test I had to remember `triage` averages over rows after the first, so a two-line sample gives a single steady row: short samples are noisy, take at least five.

## From resource to cause: profiling

Once a resource is implicated, find *which code* uses it.

- **CPU**: sampling profilers. `perf record -F 99 -g -p <pid> -- sleep 30` then `perf report`, or generate a **flame graph** (width = share of CPU samples, stack = call chain). Language-specific profilers (py-spy, async-profiler, `pprof`, `go tool pprof`) give application-level stacks. `perf top` is the live view.
- **Off-CPU / blocking**: where threads *wait*: `strace -c -p`, `offcputime` (bcc/bpftrace), `pidstat -w`, lock profilers.
- **Memory**: `smem`, `/proc/<pid>/smaps_rollup`, heap profilers (jemalloc, `heaptrack`, `tracemalloc`).
- **Disk**: `iotop`, `biolatency` and `biosnoop` (BPF), `fio` for baselines.
- **Network**: `tcpdump`, `ss -ti` (per-connection RTT/cwnd/retransmits), `tcplife` and `tcpretrans` (BPF).
- **Everything**: eBPF tools (`bpftrace`, bcc) trace kernel and user events with low overhead; they need a fairly recent kernel and root.

Prefer low-overhead sampling in production; `strace` slows the target a lot (Lesson 01), and `perf` with high frequency can too.

## Work in a loop, change one thing

1. **Define the symptom** in numbers: latency p99 from 80 ms to 900 ms starting at 14:02; error rate; throughput.
2. **Establish the baseline** and what changed (deploys, traffic, data growth, config, noisy neighbour).
3. **Walk USE** and note the resource with saturation/errors.
4. **Form a hypothesis, make a prediction, test** (a change to one variable).
5. **Verify with the symptom metric**, not only the system metric: lowering `iowait` that doesn't improve p99 wasn't the cause.
6. **Write it down** (Level 4 · 04 and 10): the cause, the fix, the detection that would have found it sooner.

Common traps: tuning before measuring; fixing a symptom (restarting) and losing the evidence; trusting averages when the tail is the problem; benchmarking on idle hardware; changing several settings at once; assuming containers' CPU/memory figures are the host's.

## How It Actually Works

Every performance counter these tools read is a kernel statistic updated as events happen: the scheduler counts run-queue length and context switches, the memory manager counts page faults and scans, the block layer records request start/finish times (giving `await` and `aqu-sz`), the network stack counts packets and drops. Tools such as `vmstat` simply sample those counters at an interval and print the
difference, which is why the first line (since boot) is an average and the rest are per-interval rates. Sampling profilers set a timer or a hardware performance counter to interrupt the CPU periodically (`-F 99` = 99 times a second), record the instruction pointer and call stack, and aggregate; statistically the hot functions appear in proportion to the time spent in them. eBPF attaches small verified programs to kernel and
user events to aggregate data in-kernel and only report summaries.

## Common mistakes

- **Starting with `top` and stopping at the first big process.**
- **Using utilization alone** and ignoring saturation and errors.
- **Reading `vmstat`'s first line** as current.
- **Optimising a component that isn't the bottleneck.**
- **Profiling with tools that slow the target** into a different problem.
- **Changing several tunables at once.**
- **No baseline** ("is 70% iowait normal here?").
- **Averaging** and missing a saturated single core or the latency tail.

## Exercise

1. On a Linux VM, create each of the four scenarios (spin loops; `fio` heavy random I/O; a program that allocates beyond RAM; high connection churn) and record `vmstat`/`iostat`/`mpstat`/`ss` output. Run the triage function on your real `vmstat` output and refine its thresholds.
2. Take a CPU profile of a slow script with `perf` (or py-spy) and produce a flame graph; identify the top three frames.
3. Write a USE checklist for a service you operate with commands and "normal" values for each resource.
4. Argue, with evidence you would collect, whether 90% `%util` on an NVMe device is a problem.
