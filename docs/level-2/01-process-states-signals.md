---
description: "Process states (running/sleeping/stopped/zombie), the real difference between SIGTERM/SIGKILL/SIGSTOP, and why a zombie can't be killed."
---

# 01 · Process States, Signals & Job Control

"Just kill it" is the standard troubleshooting reflex, and it works often enough that people rarely stop to ask why
`kill -9` sometimes does nothing to a process that's clearly still showing up in `ps`. The answer is in the
process's **state**, and in what a signal actually is: not a forceful interrupt in the way the name suggests, but
a flag the kernel sets that the target process (if it's even in a position to) gets a chance to act on.

## The states ps shows you

`ps -o stat` reports a single letter (sometimes with modifiers) for each process: **R** (running or runnable —
on a CPU or waiting for one), **S** (sleeping, waiting on some event — I/O, a timer, a lock — and not consuming
CPU meanwhile), **D** (uninterruptible sleep, almost always waiting on disk I/O — notoriously *cannot* be killed,
not even with `SIGKILL`, until the I/O completes, because the kernel considers the operation in a state too
delicate to abort safely), **T** (stopped, by a job-control or `SIGSTOP`-family signal), and **Z** (zombie — the
process has exited, but its parent hasn't yet collected its exit status).

## Worked example: stopping, continuing, and a real zombie

```text
$ sleep 60 &
$ ps -o pid,stat,comm -p $!
    PID STAT COMMAND
 242322 S    sleep

$ kill -STOP $!
$ ps -o pid,stat,comm -p $!
    PID STAT COMMAND
 242322 T    sleep

$ kill -CONT $!
$ ps -o pid,stat,comm -p $!
    PID STAT COMMAND
 242322 S    sleep

$ ps -p 2181 -o pid,ppid,stat,comm
    PID    PPID STAT COMMAND
   2181       1 Ss   sshd-session

$ ps -p 2188 -o pid,ppid,stat,comm
    PID    PPID STAT COMMAND
   2188    2181 Z    sshd

$ cat /proc/2188/status | grep -E "^(Name|State|PPid)"
Name:	sshd
State:	Z (zombie)
PPid:	2181
```

(Real output from this course's lab VM — the zombie above wasn't staged; it's a genuine leftover sshd child from an
earlier SSH session on this machine, caught in the act.) `kill -STOP`/`-CONT` flip the target between `S` and `T`
directly and observably — this is exactly what shell job control's `Ctrl-Z` (stop) and `fg`/`bg` (continue) do
under the hood. The zombie is the more interesting case: PID 2188's state is unambiguously `Z (zombie)`, its parent
(2181, `sshd-session`) is still alive and well, and yet nothing you run **against PID 2188 itself** — `kill -9
2188` included — will make it disappear. A zombie has no running code left to signal; it's a corpse of
accounting information (exit status, resource usage) that the kernel is required to keep until something calls
`wait()` on it. The only way to clear a zombie is for its parent to reap it (call `wait()`/`waitpid()`) — or for
the parent itself to die, which reparents the zombie to PID 1 (Lesson 7, Level 1), whose entire job includes
reaping orphans like this one.

## How It Actually Works

Signals are, at the implementation level, bits set in a per-process pending-signal bitmask, checked by the kernel
at specific points (returning from a syscall, returning from an interrupt) rather than delivered instantly the
moment `kill()` is called. A process can **block** a signal (defer its delivery), **ignore** it, or install a
**handler** (a function the kernel calls instead of taking the default action) — for every signal except two:
`SIGKILL` (9) and `SIGSTOP` (19) are deliberately **unblockable and unhandleable**, which is exactly why they're
the reliable "last resort" signals; every other signal's behavior, including the supposedly-polite `SIGTERM` (15),
is only a *request* that a well-behaved process chooses to honor by exiting cleanly, and a process that's hung,
ignoring signals, or stuck in uninterruptible sleep (`D` state, usually deep in a kernel-level I/O wait) can
simply not respond to `SIGTERM` or even `SIGKILL` until the kernel operation it's blocked on completes on its own.

This is also why `kill -9` has a reputation as "the nuclear option" rather than the *correct default*: because the
process gets no chance to run its own exit handler, open files aren't necessarily flushed cleanly, temp files
aren't cleaned up, and locks aren't released gracefully — `SIGTERM` first, giving the application a chance to shut
down in an orderly way, with `SIGKILL` only as the fallback when `SIGTERM` is ignored, is the standard and correct
escalation (and is literally what `systemd` does to a service that won't stop, after `TimeoutStopSec` expires —
Level 2's `systemd` lessons return to this).

## Common mistakes

- **Assuming `kill -9` always works immediately.** It does not against a zombie (there's no process left to kill)
  and does not against a process stuck in `D` state (uninterruptible sleep) until the underlying I/O resolves —
  in both cases the process will appear to "ignore" `SIGKILL`, which is a real and diagnosable state, not a bug
  in `kill`.
- **Confusing a zombie process with a resource leak you need to urgently fix by force.** A *few* short-lived
  zombies awaiting reaping are completely normal; what matters is whether the parent eventually reaps them. A
  large, growing number of permanent zombies under one parent is the real signal of a bug — that parent isn't
  calling `wait()` at all.
- **Sending `SIGSTOP` to a process and forgetting about it.** A stopped process holds onto any resources it had
  (memory, open files, locks) indefinitely, invisible in `top`'s CPU column (it's not consuming any), until someone
  remembers to `SIGCONT` it or kills it outright.

## Exercise

Start a `sleep 120 &` job, and in order: check its `STAT` with `ps`, stop it with `kill -STOP`, confirm the state
changed, continue it with `kill -CONT`, confirm it changed back, then let it finish naturally or kill it. Separately,
search your own system for zombies with `ps -eo pid,ppid,stat,comm | awk '$3 ~ /Z/'`; if you find one, identify its
parent and form a hypothesis for why that parent hasn't reaped it yet.
