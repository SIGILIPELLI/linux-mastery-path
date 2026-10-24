---
description: "Diagnosing a real hung process through /proc alone — open files, what it's waiting on, and its current syscall — with no debugger attached."
---

# 05 · /proc and /sys as Debugging Tools

Level 1 introduced `/proc` as a live, kernel-generated view of process state. This lesson uses it for what it's
actually for in practice: figuring out what a specific, currently-running process is doing, what it has open, and
exactly what it's blocked on — without attaching a debugger, without the process's cooperation, and without
stopping it.

## Worked example: diagnosing a real process from the outside

```text
$ python3 -c "
import socket, time
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('127.0.0.1', 9911))
s.listen(1)
f = open('/tmp/debugtest.txt', 'w')
f.write('partial data')
time.sleep(60)
" &

$ cat /proc/$PID/status | grep -E "^(Name|State|VmRSS)"
Name:	python3
State:	S (sleeping)
VmRSS:	   12004 kB

$ ls -l /proc/$PID/fd
lr-x------  0 -> /dev/null
l-wx------  1 -> pipe:[743620]
l-wx------  2 -> pipe:[743621]
lrwx------+ 3 -> socket:[744581]
l-wx------  4 -> /tmp/debugtest.txt

$ cat /proc/$PID/wchan
hrtimer_nanosleep

$ sudo cat /proc/$PID/syscall
115 0x1 0x1 0xffffe67c3a10 0x0 0x0 0x0 0xffffe67c39d0 0xef2e973b8464
```

(Real output from this course's lab VM — this process was never told it was being inspected.) Without touching
the process at all, `/proc/$PID/fd` reveals exactly what it has open: a listening socket (fd 3) and a real file
it opened for writing (fd 4, `/tmp/debugtest.txt`) — information you could otherwise only get by reading the
program's source and trusting it matches what's actually running. `wchan` ("wait channel") names the specific
kernel function the process is currently blocked inside — `hrtimer_nanosleep` here, directly confirming it's
genuinely asleep inside a timer wait, exactly matching the `time.sleep(60)` in the script, not stuck on I/O or a
lock. `/proc/$PID/syscall` goes one level deeper, showing the raw syscall number and argument registers the
process is currently inside — syscall `115` on this architecture is the nanosleep-family syscall, consistent with
everything else observed. Notice the **first** attempt at reading `/proc/$PID/syscall` from this same shell
session, without `sudo`, was refused with "Operation not permitted" — a real, observed restriction from the
kernel's Yama security module (`ptrace_scope`), which by default on Ubuntu only allows a process to inspect this
level of detail about a **direct ancestor/descendant**, not an arbitrary sibling process started from the same
shell — `sudo` bypassed that restriction by inspecting as root.

## How It Actually Works

Every one of these files is generated live by the kernel reading its own internal data structures for that
specific process — `/proc/$PID/fd` is literally the kernel's per-process file-descriptor table, rendered as
symlinks; `/proc/$PID/status` is formatted straight from the kernel's `task_struct`; `wchan` and `syscall` expose
the process's current execution context captured the instant you read them. This is fundamentally different from
attaching a debugger (which typically *stops* the target to inspect it) — reading `/proc` doesn't pause anything,
which is exactly why it's the right first tool for diagnosing a production process you can't afford to freeze,
even briefly, for a full debugger attach.

The Yama `ptrace_scope` restriction encountered above exists because the level of detail `/proc/$PID/syscall`
(and especially full `ptrace()` attachment, which can read and *write* another process's memory) exposes is
genuinely security-sensitive — without some restriction, any process you run could inspect, and potentially
manipulate, any other process you're running, including things like a password manager or SSH agent holding
sensitive data in memory. "Restricted" mode (the common default) narrows this to direct ancestor/descendant
relationships specifically because that covers the overwhelmingly common legitimate case (a debugger attaching
to a process it started, or a supervisor inspecting its own child) while still blocking an unrelated,
possibly-compromised process from snooping on a sibling.

## Common mistakes

- **Reaching for `gdb` or another full debugger-attach workflow for questions `/proc` alone already answers.**
  "What files does this have open," "is it actually sleeping or stuck," and "what was its last known address
  space layout" are all answerable from `/proc` with zero risk of pausing or disturbing the process — save a
  full attach for when you actually need to set breakpoints or inspect variables.
- **Being surprised by a Yama-related "Operation not permitted" and assuming something is broken.** As shown
  above, this is an intentional, expected security restriction on several `/proc/<pid>/` files and on `ptrace()`
  attachment generally — `sudo`, or running the inspecting tool as a genuine ancestor of the target process, is
  the normal, supported way past it, not a bug workaround.
- **Reading `/proc/<pid>/fd` once and assuming the open-file picture is static.** A long-running process can
  open and close files continuously — a single snapshot tells you the state at that instant, not the full
  history; repeated sampling (or `lsof`'s own snapshot, which reads the same underlying data) is needed to catch
  a transient issue.

## Exercise

Start any long-running command that sleeps or blocks (`sleep 60 &` is enough, or something that opens a file and
waits), and from another terminal, inspect its `/proc/$PID/status`, `/proc/$PID/fd`, and `/proc/$PID/wchan`
without stopping it. Then try reading `/proc/$PID/syscall` both without and with `sudo`, and if you hit the same
"Operation not permitted" this lesson did, check your system's `ptrace_scope` value at
`/proc/sys/kernel/yama/ptrace_scope` and relate the number there to the restriction you just observed.
