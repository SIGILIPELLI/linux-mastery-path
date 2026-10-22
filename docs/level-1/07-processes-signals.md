---
description: "Processes, zombies and orphans, exit codes, signals, trap and job control, demonstrated on macOS."
---

# 07 · Processes, Signals & Job Control

Everything running on a Linux system is a **process**: an instance of a program with its own memory, open files, environment and credentials. Knowing how
processes are created, how they end, and how to ask them politely or forcibly to stop is the core of operating a server.

!!! note "What was run"
    The process experiments below (zombies, orphans, signals, exit codes, `trap`, job control, environment inheritance) were **run on
    macOS**, whose process model follows POSIX like Linux's. Output formats of `ps` differ on Linux (`ps aux`, `ps -ef`, `pstree`, `/proc/<pid>/status` are described from
    man pages and not run). See Lesson 01.

## Creating processes: fork and exec

A new process is born by `fork()` (a copy of the caller) and usually immediately `exec()`s a new program. The shell does exactly that for each command. Every process has a **PID**, a
**parent PID (PPID)**, a process group and session. PID 1 is the init system (systemd on most distributions), the ancestor of everything else.

```text
ps -o pid,ppid,stat,comm -p $$        (run: the current shell)
  PID  PPID STAT COMM
96872 96870 S    bash
```

`STAT` shows the state. Common Linux states: `R` running/runnable, `S` interruptible sleep, `D` uninterruptible sleep (usually waiting on I/O; can't be killed), `T` stopped, `Z` zombie.

### Zombies and orphans (run)

A **zombie** is a process that has exited but whose parent hasn't collected its exit status with `wait()`. I made one: a Python parent forked a child that exited immediately,
then slept without waiting:

```text
  PID  PPID STAT COMM
96877 96876 Z    <defunct>
after wait: PID STAT        <- the entry is gone once the parent called waitpid()
```

The `Z` / `<defunct>` entry holds only the exit status in the process table. You cannot `kill` a zombie (it's already dead). The fix is for the parent to `wait()`, or for
the parent to exit so the zombie is adopted and reaped by init. A growing pile of zombies means a buggy parent (a common issue for PID 1 inside containers that don't reap children;
Level 4 · 09).

An **orphan** is a live process whose parent died. It's re-parented to PID 1 (or a subreaper). Run: a bash parent started `sleep 5 &` and exited; `ps` then showed the sleeper with `PPID 1`:

```text
96881     1 sleep
```

## Exit status

A process ends with an exit code 0-255; `0` means success. Run results:

| Situation | `$?` |
|---|---|
| `exit 3` | `3` |
| Command not found | `127` |
| File exists but isn't executable | `126` |
| Killed by signal N | `128 + N` (SIGSEGV: `139`, SIGTERM: `143`, SIGKILL: `137`) |

The `128+N` convention is how shells report signal deaths, and it explains why a container exiting with `137` was killed (often by the OOM killer, Level 3 · 02) and `143` was a clean SIGTERM stop.

## Signals

Signals are small asynchronous notifications. The ones you use:

| Signal | Number | Default | Meaning / use |
|---|---|---|---|
| SIGTERM | 15 | terminate | "Please shut down" (the default of `kill`); can be caught for graceful shutdown |
| SIGKILL | 9 | terminate | Immediate, **cannot be caught or ignored**; no cleanup |
| SIGINT | 2 | terminate | Ctrl+C |
| SIGHUP | 1 | terminate | Terminal hangup; many daemons re-read config on HUP |
| SIGSTOP / SIGCONT | 19 / 18 (Linux) | stop / resume | Ctrl+Z sends SIGTSTP |
| SIGUSR1/2 | 10/12 (Linux) | terminate | Application-defined |
| SIGCHLD | 17 (Linux) | ignore | A child changed state |
| SIGPIPE | 13 | terminate | Writing to a pipe nobody reads |

Signal **numbers differ between systems** for some signals (`kill -l` on the Mac lists `7) SIGEMT`, a BSD signal Linux doesn't have), so use names in scripts.

Test (run): `sleep 30 &` then `kill -TERM $!` gave exit `143` (128+15), and `kill -KILL` gave `137` (128+9). A process can **catch** TERM and clean up:

```bash
( trap 'echo got-TERM; exit 7' TERM; sleep 30 & wait ) &
kill -TERM $!         # prints got-TERM; the subshell exits with 7   (run)
```

`trap` can't catch SIGKILL, so always send TERM first, wait a grace period, and only then KILL. This is also what orchestrators do (Kubernetes sends TERM, waits the grace period, then KILL).
A script's `trap ... EXIT` is the idiomatic way to remove temp files.

Why `wait` in that example? A shell running a foreground child doesn't run its trap until the child finishes; backgrounding the child and `wait`ing makes the trap run immediately.

### Killing a parent does not kill its children (run)

`bash -c 'sleep 40 & sleep 40 & wait'` started two children; `kill -TERM` on the bash parent terminated it, and `pgrep -P <parent>` then showed **0** children, yet the sleeps were still
running (I had to `pkill` them): they were orphaned and re-parented. To stop a whole tree, signal the **process group**: `kill -TERM -- -<pgid>` (negative PID), or run
services under a supervisor (systemd kills the whole cgroup; Level 2 · 02) rather than by hand.

## Job control

Interactive shells manage background and suspended jobs:

```bash
sleep 100 &        # run in background; $! holds its PID
jobs               # [1]+ Running   sleep 100 &          (run)
fg %1 ; bg %1      # bring to foreground / resume in background
Ctrl+Z             # suspend the foreground job (SIGTSTP)
nohup cmd &        # keep running after the terminal closes (ignores SIGHUP)
disown %1          # remove from the shell's job table so it won't get HUP
```

For anything that must survive logout, don't rely on `nohup`; use a service manager or `tmux`/`screen` for interactive sessions (Level 2).

## Environment and inheritance

A child inherits an *exported* copy of the parent's environment, never the reverse. Run:

```text
X=1; bash -c 'echo "unexported:[$X]"'   ->  unexported:[]
export X;  bash -c 'echo "exported:[$X]"'   ->  exported:[1]
```

A child's `cd` or variable changes never affect the parent (`(cd /tmp; pwd)` printed `/tmp` but the shell stayed put). `source file` runs a script in the *current* shell, which is how
environment files are loaded.

## Priorities

`nice -n 10 cmd` lowers a process's CPU priority (range -20 highest to 19 lowest; only root can lower the number), and `renice` changes it live. It affects only CPU
scheduling among runnable processes (Level 3 · 04), not I/O (`ionice`) or memory.

## Inspecting processes on Linux (not run)

```bash
ps aux --sort=-%mem | head          # biggest memory users
ps -eo pid,ppid,stat,wchan:20,cmd   # what kernel function each sleeping process waits in
pstree -p                           # the tree
pgrep -af nginx ; pkill -TERM -f myapp
cat /proc/<pid>/status ; ls -l /proc/<pid>/fd ; cat /proc/<pid>/limits
```

## How It Actually Works

The kernel keeps a `task_struct` per thread (threads are processes sharing memory, created with `clone`). `fork` duplicates the descriptor and memory mappings
**copy-on-write**, so it's cheap. When a process exits, the kernel frees its memory and files but keeps the small task entry with the exit code until the parent calls `wait` (the
zombie). Signals are bits in a pending-signal mask checked when a process returns to user mode: the kernel either runs the registered handler, takes the default action, or ignores the signal. SIGKILL and SIGSTOP
are handled in the kernel and cannot be intercepted. A process in `D` state (uninterruptible sleep, typically inside a driver waiting on a disk or NFS) won't act on signals until the
operation completes, which is why a hung NFS mount can leave unkillable processes (Level 4 · 06).

## Common mistakes

- **`kill -9` first**, skipping cleanup and leaving locks, temp files and half-written data.
- **Killing only a parent** and leaving children running.
- **Trying to kill zombies** instead of fixing the parent.
- **`nohup` as service management**: no restart, no logs, no dependency handling.
- **Expecting environment changes in a child to affect the parent.**
- **Treating exit code 1 vs 126/127/137** all as "failed" and missing the cause.
- **Using signal numbers** in scripts that run on both Linux and BSD/macOS.

## Exercise

1. Write a script that traps TERM and INT, prints a message and removes a temp file, then loops forever. Stop it with `kill`, then `kill -9` on a second copy and compare what happened to the temp file.
2. Reproduce the orphan experiment, then kill a whole process group in one command.
3. Make `ps` show a zombie on your machine using the Python snippet idea; then make the parent reap children with a `SIGCHLD` handler.
4. On Linux, find a process in `D` state (or simulate with a slow NFS mount) and read `/proc/<pid>/wchan`; explain why `kill -9` doesn't help.
