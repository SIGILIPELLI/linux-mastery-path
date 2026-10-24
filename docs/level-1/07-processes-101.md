---
description: "Processes 101: PIDs and PPIDs, fork/exec, the process tree, and what PID 1 actually does on a running Linux system."
---

# 07 · Processes 101: PIDs, fork/exec & the Process Tree

Every running program on Linux is a **process**, and every process except one was created by exactly one other
process calling `fork()`. Understanding that one mechanism — fork, then usually exec — explains where processes
come from, why every process has a parent, and what "PID 1" means and why it matters so much that systems treat
losing it as fatal.

## fork() and exec(): two different jobs, often used together

`fork()` makes an almost-exact copy of the calling process: same memory contents, same open file descriptors, same
environment — but a new PID, and a return value that tells the two now-separate processes apart (the child gets
`0`, the parent gets the new child's PID). Right after a fork, you have two processes running the *same program*.
That's rarely what you actually want, which is why fork is almost always followed immediately by `exec()`: exec
doesn't create a new process at all — it **replaces** the calling process's program code and memory with a
different program, keeping the same PID. The combination — fork to get a new process, exec to make it run
something else — is literally how your shell starts every command you type.

## Worked example: watching PIDs, PPIDs, and the process tree

```text
$ ps -ef --forest | head -n5
UID          PID    PPID  C STIME TTY          TIME CMD
root           2       0  0 23:26 ?        00:00:00 [kthreadd]
root           3       2  0 23:26 ?        00:00:00  \_ [pool_workqueue_release]
root           4       2  0 23:26 ?        00:00:00  \_ [kworker/R-rcu_gp]
...

$ ps -p 1 -o pid,ppid,comm
    PID    PPID COMMAND
      1       0 systemd

$ echo "parent pid via \$\$: $$"
parent pid via $$: 10457

$ (echo "subshell BASHPID: $BASHPID"; ps -o pid,ppid,comm -p $BASHPID)
subshell BASHPID: 10472
    PID    PPID COMMAND
  10472   10457 ps
```

(Real output from this course's lab VM.) `ps -ef --forest` draws the tree by `PPID`: `kthreadd` (PID 2) is the
kernel's own thread-spawning helper, parent to a long list of kernel worker threads — these aren't started by
`fork()`/`exec()` from userspace at all, which is why they show up in brackets and have no real command line.
`ps -p 1` shows `systemd` as **PID 1**, with `PPID 0` — the only process on the whole system whose parent is "the
kernel itself" rather than another process, because PID 1 is the one process the kernel starts directly during
boot (Lesson 2), and every other process traces its ancestry back to it through a chain of fork calls. The last two
commands show something subtler and genuinely easy to get wrong: the subshell's *own* PID, read via `$BASHPID`
(10472), correctly reports its parent as 10457 — the outer shell's `$$` — when asked through `ps`, which queries
the kernel's live process table directly. (`$PPID` as a bash *variable*, by contrast, is set once when a shell
starts and is not guaranteed to update inside subshells the way you'd expect — a good reason to trust `ps`/`/proc`
over shell variables when the exact parent matters.) Also notice `ps` itself is reported as the COMMAND running
under PID 10472, the subshell's own PID — bash optimized away a second fork for that trailing external command and
had the subshell process `exec` directly into `ps`, reusing the same PID rather than forking yet again.

## How It Actually Works

`fork()` is implemented using **copy-on-write**: the kernel doesn't actually duplicate the parent's memory pages the
instant you call fork. Instead, both parent and child start out sharing the exact same physical memory pages,
marked read-only. Only when either process tries to *write* to a shared page does the kernel step in, actually copy
that one page, and let the write proceed against the private copy. This is why `fork()` is cheap even for a process
using gigabytes of memory — a classic use case (a database doing a `fork()`-based backup snapshot) relies on this
directly: the child gets what's effectively an instant, consistent point-in-time view of the parent's memory,
without the kernel physically copying anything unless and until something changes.

PID 1 is special for a reason that goes beyond just "it started first." The kernel gives PID 1 **reaping**
responsibility for one case other processes can't opt out of: when any process's parent dies before the child does,
the child is **reparented to PID 1** (historically; on modern Linux, to the nearest surviving ancestor marked as a
"subreaper," which is usually still PID 1 in practice). This matters because every process, when it exits, leaves
behind an exit status that its parent is expected to collect with `wait()` — a process that has exited but hasn't
been "waited for" yet is a **zombie** (state `Z` in `ps`), and it stays a zombie, consuming a slot in the process
table, until its parent collects it. If the original parent is gone, PID 1 inherits the job of eventually reaping
that orphan. This is also exactly why container images that run a single application directly as PID 1, without a
real init system, can leak zombie processes under load — the application was never written to reap children it
didn't directly spawn, and nothing else in the container is positioned to do it; it's the standard justification
for tools like `tini` or `dumb-init` as a container's actual PID 1.

## Common mistakes

- **Trusting `$PPID` inside a subshell or pipeline for exact process relationships.** As shown above, it's a shell
  variable set at shell-start time, not a live kernel query — `ps -o ppid= -p $BASHPID` or reading
  `/proc/self/status`'s `PPid:` field gives you the real, current answer.
- **Assuming kernel threads (shown in `[brackets]` by `ps`) are "processes" in the same sense as your shell or a
  web server.** They share the kernel's address space, were never `fork()`ed from userspace, and don't have a
  command line — tools and monitoring that assume every PID has an `argv` will misbehave on them.
- **Running an application directly as PID 1 inside a container without reaping logic**, then being confused by
  slowly accumulating zombie processes (visible as `Z` state in `ps`) that never get collected because nothing with
  reaping responsibility is watching for them.

## Exercise

Run `ps -ef --forest` on any Linux machine and find the longest unbroken parent-child chain from PID 1 down to a
leaf process you recognize (your own shell is a good target). Then run `ps -eo pid,ppid,stat,comm | awk '$4 ~ /Z/'`
to check for zombies (there usually aren't any on a healthy desktop/server — if you find one, look up its parent
with `ps -o comm= -p <ppid>` and consider why that parent might not be reaping it).
