---
description: "strace tracing real syscalls (including a genuine failed one), and perf stat on a real workload — plus an honest hardware-counter limitation hit in a VM."
---

# 02 · Tracing & Profiling: strace, ltrace & perf

When a program is slow, hung, or doing something unexplained, the tools from the previous lesson tell you *that*
something is wrong at the system level. `strace`, `ltrace`, and `perf` tell you *what the program itself is
actually doing* — every syscall, every library call, or exactly where CPU time inside it is going — with no
guesswork, because they observe the real, running process directly.

## Worked example: strace on a real, ordinary command

```text
$ strace -c ls /tmp > /dev/null
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ------------------
  1.04    0.000026           8         3           sigaltstack
...
100.00    0.002494          15       159        12 total

$ strace -e trace=open,openat cat /etc/hostname
openat(AT_FDCWD, "/proc/self/maps", O_RDONLY|O_CLOEXEC) = 3
openat(AT_FDCWD, "/usr/share/coreutils/locales/uucore/en-US.ftl", O_RDONLY|O_CLOEXEC) = 3
openat(AT_FDCWD, "/usr/share/coreutils/locales/cat/en-US.ftl", O_RDONLY|O_CLOEXEC) = -1 ENOENT (No such file or directory)
openat(AT_FDCWD, "/etc/hostname", O_RDONLY|O_CLOEXEC) = 3
lima-linuxlab
```

(Real output from this course's lab VM.) `strace -c` summarizes **every syscall a process made**, with counts and
timing — `ls /tmp`, one of the simplest commands imaginable, still made **159 total syscalls and hit 12 errors**,
which is a genuinely useful thing to internalize: even "simple" programs touch the kernel far more than their
visible output suggests (locale lookups, memory-mapping shared libraries, checking terminal capabilities).
Filtering to just `open`/`openat` on `cat /etc/hostname` catches something real and specific: a failed lookup for
a locale translation file (`.../locales/cat/en-US.ftl`, `ENOENT`) that `cat` apparently tries and silently
tolerates before successfully opening the actual target file — a real, harmless-but-visible example of exactly
the kind of "why is this program touching that path" question `strace` answers directly, with evidence, instead
of by guessing from documentation.

## Worked example: perf stat, and a real, honest hardware limitation

```text
$ sudo perf stat -- bash -c "for i in \$(seq 1 500000); do :; done"

 Performance counter stats for 'bash -c for i in...':
               449      context-switches
                 0      cpu-migrations
              1974      page-faults
            446.91 msec task-clock                 #   1.0 CPUs utilized
   <not supported>      cpu-cycles

       0.444195236 seconds time elapsed
       0.435511000 seconds user
       0.014007000 seconds sys
```

(Real output — this is a genuine limitation of this lab's environment, not a staged omission.) Several metrics
worked perfectly: real context-switch and page-fault counts, real task-clock and wall-time figures. But
**`cpu-cycles` reports `<not supported>`** — this VM's hypervisor (Apple's `vz` virtualization framework,
running this course's lab VM) doesn't expose the hardware performance-monitoring unit (PMU) counters to the
guest kernel, so `perf` genuinely cannot count raw CPU cycles here, no matter how the command is invoked. This is
a real, common constraint on virtualized and especially cloud environments — some `perf` hardware events work
everywhere (software-tracked ones like context-switches and page-faults), and some depend on PMU access the
hypervisor may or may not pass through, which is worth knowing *before* concluding `perf` itself is broken on an
unfamiliar system.

## How It Actually Works

`strace` works by attaching to a process via the `ptrace()` syscall and intercepting every syscall entry and exit
— which is precise and complete, but genuinely slows the traced process down (sometimes drastically, for
syscall-heavy workloads), because every single syscall now round-trips through the tracer. `ltrace` works
similarly but at the **dynamic library call** layer instead of the syscall layer, intercepting calls into shared
libraries via their PLT (procedure linkage table) entries — useful for "what is this program calling in
`libcurl`," but it only sees dynamically-linked calls, so a statically-linked binary or a function the compiler
inlined won't show up at all.

`perf` takes a fundamentally different approach for CPU profiling specifically: rather than intercepting every
event (which would be prohibitively slow for CPU-cycle-level granularity), `perf record` uses **statistical
sampling** — periodically interrupting the running program (driven by a hardware or software timer) and
recording where it was at that instant, building up a probabilistic picture of where time is actually spent
across thousands of samples, with far lower overhead than full tracing. This is also exactly why `perf`'s CPU
profiling features need those hardware PMU counters this lab's VM couldn't provide — accurate cycle-based
sampling depends on the CPU itself generating the sampling interrupts, which pure software can't substitute for
without losing accuracy.

## Common mistakes

- **Running `strace` on a latency-sensitive production process without understanding the slowdown it causes.**
  `ptrace`-based tracing can be a real, measurable performance hit — reach for it on a copy, a canary, or
  briefly and deliberately, not as a default first troubleshooting step on live traffic.
- **Assuming `ltrace`'s silence on a function means it was never called.** As covered above, statically-linked
  code and compiler-inlined calls are invisible to PLT-based interception — a negative `ltrace` result doesn't
  rule out the function running, it only rules out a *dynamically-linked, PLT-visible* call to it.
- **Blaming `perf` itself when hardware counters report `<not supported>` in a VM or container.** As this
  lesson's real output shows, this is frequently a hypervisor/PMU-passthrough limitation, not a `perf`
  installation problem — software events (context-switches, page-faults, task-clock) remaining available while
  hardware events don't is the normal signature of this specific limitation.

## Exercise

Run `strace -c` against any command on a Linux machine and find the syscall with the highest total time, not
just the highest call count — they're often different, and the gap itself is informative (many cheap calls vs.
one slow one). Then run `perf stat` against a short CPU-bound loop and check whether `cpu-cycles` reports a real
number or `<not supported>` on your system — if supported, compare it against the same loop run inside a VM, and
note the difference this lesson's environment hit.
