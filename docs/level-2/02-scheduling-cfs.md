---
description: "Niceness vs real scheduling priority, how renice changes a running process, and how the Completely Fair Scheduler picks what runs next."
---

# 02 · Scheduling: Nice, Priorities & the CFS

"Nice" is a strange name for a number that goes from -20 to 19, until you learn where it comes from: a *higher*
value means you're being more generous — more "nice" — to everyone else on the system, by asking for a smaller
share of the CPU. It's one knob, among several the kernel actually uses, and the gap between what you set and
what the kernel does with it is where most of the confusion about process scheduling lives.

## nice and real priority are not the same number

`nice` is the number you set, from **-20** (most aggressive, highest claim on the CPU) to **19** (most
accommodating, lowest claim). It is *not* what the kernel schedules against directly — the scheduler works with an
internal, kernel-level priority derived from nice (and, for Linux's default scheduler, from a weight table used to
compute how much virtual runtime a process accumulates). `ps -o ni,pri` shows both: `ni` is the number you set,
`pri` is procps's view of the resulting kernel-level priority.

## Worked example: setting and changing niceness on real processes

```text
$ nice -n 10 sleep 5 &
$ ps -o pid,ni,pri,comm -p $!
    PID  NI PRI COMMAND
 244284  10   9 sleep

$ sleep 5 &
$ ps -o pid,ni,pri,comm -p $!
    PID  NI PRI COMMAND
 244287   0  19 sleep

$ renice -n 15 -p 244287
244287 (process ID) old priority 0, new priority 15
$ ps -o pid,ni,pri,comm -p 244287
    PID  NI PRI COMMAND
 244287  15   4 sleep

$ chrt -p $$
pid 244269's current scheduling policy: SCHED_OTHER
pid 244269's current scheduling priority: 0
```

(Real output from this course's lab VM.) Default niceness is `0`, reported here as `PRI 19`; asking for `nice -n
10` dropped the reported priority to `9`, and `renice`-ing a *running* process from `0` to `15` dropped its
priority further to `4` — in this `ps` output, lower `PRI` consistently tracks higher (less favorable) `nice`.
`renice` is the proof that niceness isn't a one-time launch-time setting: you can lower (be nicer) or, as root,
raise the priority of any already-running process at any time, which is exactly what you'd reach for to deprioritize
a batch job that's already hogging CPU without having to restart it. `chrt -p` shows the *scheduling policy* for
the current shell: `SCHED_OTHER`, the default time-shared policy almost every normal process uses — Linux also
supports real-time policies (`SCHED_FIFO`, `SCHED_RR`) for processes that need deterministic, priority-based
preemption instead of fair time-sharing, used by things like audio processing or industrial control software
where "fair" isn't the goal, "on time" is.

## How It Actually Works

The default Linux scheduler for `SCHED_OTHER` processes is the **Completely Fair Scheduler (CFS)** (as of recent
kernels, CFS's accounting has been reworked under the "EEVDF" scheduling class, but the fairness goal and the
nice-to-weight relationship described here still hold). CFS doesn't use fixed time slices doled out round-robin;
it tracks each process's **virtual runtime** — accumulated CPU time, scaled by a weight derived from its nice
value — and always picks the process with the *smallest* virtual runtime to run next. A process with a less
favorable (higher) nice value accumulates virtual runtime faster for the same real CPU time, which means it gets
picked less often relative to others — nice values map onto actual CPU share through a fixed weight table where
each nice-value step is roughly a 10% change in CPU share relative to its neighbor, not a linear "nice 10 gets 10%
less" relationship.

This design is also why CFS is called "completely fair" with a straight face even though it's constantly making
processes wait: fairness here means "no process accumulates a disproportionate share of actual CPU time relative to
its weight," enforced continuously via a red-black tree keyed by virtual runtime (so "find the process with the
least runtime so far" is an efficient tree lookup, not a linear scan) — not "every process gets an equal, fixed
timeslice" the way older round-robin schedulers worked. Real-time policies (`SCHED_FIFO`/`SCHED_RR`) sit entirely
outside this fairness model: any runnable real-time-scheduled process will always preempt any `SCHED_OTHER`
process, regardless of nice value, which is exactly the point — and exactly why a buggy real-time process that
never blocks or yields can starve an entire system, a well-known hazard that's part of why real-time scheduling
privileges are normally restricted to root.

## Common mistakes

- **Expecting a precise, linear relationship between nice value and CPU percentage.** The actual effect depends on
  what else is runnable at the same time and the weight table's (roughly multiplicative, not linear) scaling — nice
  is a relative claim on CPU among competing processes, not an absolute percentage guarantee, and a nice-19 process
  with the CPU all to itself still gets 100% of it.
- **Setting real-time priority (`chrt -f`/`chrt -r`) on a process "to make it faster" without understanding
  starvation risk.** A real-time process that spins without yielding can lock out everything else on that CPU,
  including, in bad cases, the kernel's own housekeeping work — this is a sharp tool, not a faster version of
  `nice`.
- **Forgetting that lowering niceness (toward -20, a higher CPU claim) requires root**, while raising it (toward
  19, being "nicer") doesn't — an unprivileged user can deprioritize their own processes freely but can't grab a
  bigger CPU share without elevated privilege, which is a deliberate anti-abuse design, not an arbitrary limitation.

## Exercise

Launch two CPU-bound loops at the same time (`yes > /dev/null &` twice, or any busy-loop you like) on a
single-core-limited cgroup or VM so they actually compete for the same CPU. Renice one of them to `19` and watch
`top`'s CPU% column for both over the next several seconds — predict the rough proportion before you look.
