---
description: "System calls and the kernel boundary: strace, errno, measured call overheads, lazy mmap allocation and copy-on-write fork, run on macOS."
---

# 01 · System Calls & the Kernel Boundary

Every useful thing a program does, such as opening a file, sending a packet, starting a process or allocating memory, requires the kernel. Programs ask by making **system calls**. Seeing the system calls a program makes is the single most useful debugging technique on Linux,
because it shows what the program *actually* does rather than what its source or documentation claim.

!!! note "What was run"
    `strace`, `ltrace` and `perf trace` are Linux tools and **were not run**. The measurements below ran on **macOS (Apple Silicon)** with Python: call timings, a lazy-allocation experiment and a `fork` timing. macOS has different system calls and a 16 KiB page size, and these
    numbers describe that machine only; they show shapes, not Linux figures. System-call semantics come from the Linux man-pages project (man7.org, section 2; October 2026). See Level 1 · Lesson 01.

## The boundary

User programs run in **user mode** with no direct access to hardware or other processes' memory. To do privileged work they execute a special CPU instruction (`syscall` on x86-64, `svc` on ARM64) that traps into the kernel, which validates arguments, performs the operation, and returns. The
C library wraps these: `open()` in libc becomes the `openat` system call; `printf()` buffers in user space and eventually calls `write`.

| Area | Typical system calls (man section 2) |
|---|---|
| Files | `openat`, `read`, `write`, `close`, `stat`, `lseek`, `fsync`, `unlink`, `rename` |
| Processes | `clone`/`fork`, `execve`, `wait4`, `exit_group`, `kill` |
| Memory | `mmap`, `munmap`, `brk`, `mprotect` |
| Networking | `socket`, `bind`, `listen`, `accept4`, `connect`, `sendto`, `recvfrom` |
| Waiting / events | `poll`, `epoll_wait`, `futex`, `nanosleep` |
| Identity / security | `setuid`, `capget`, `prctl`, `seccomp` |

Linux has a few hundred system calls; they are the entire interface between applications and the kernel, which is why **containers, sandboxes (seccomp) and tracing all work at this boundary**.

## Seeing syscalls with strace (not run)

```bash
strace -f -o /tmp/trace.txt ls /nonexistent          # -f follows child processes
strace -c ls /usr                                     # summary: count and time per syscall
strace -e trace=openat,connect,execve -f myprog       # only the calls you care about
strace -p 1234                                        # attach to a running process (needs permission)
strace -tt -T myprog                                  # timestamps and time spent in each call
```

A trace line looks like `openat(AT_FDCWD, "/etc/app.conf", O_RDONLY) = -1 ENOENT (No such file or directory)`: the call, its arguments, the return value, and for failures the **errno** name and text. That one line routinely solves problems like "where does it look for its config?" (the program tried six paths and failed
on all of them), "why is it slow?" (a `connect` that waits 30 s on DNS), and "why Permission denied?" (the path and flags it used). On macOS the closest tool is `dtruss` (needs root and SIP exceptions) or `fs_usage`; neither was usable in my environment.

### errno

A failed system call returns `-1` (in libc) and sets `errno`. The common ones: `ENOENT` no such file, `EACCES`/`EPERM` permission denied / operation not permitted, `EEXIST`, `ENOSPC` no space left, `EMFILE`/`ENFILE` too many open files, `ECONNREFUSED`, `ETIMEDOUT`, `EADDRINUSE`, `EINTR` interrupted by a signal, `EAGAIN` try again. The
earlier lessons' error messages (Lesson 06's "Connection refused", "Address already in use") are literally strerror text for these.

## Measuring the boundary (run on macOS)

A Python micro-benchmark of different calls, 200,000 iterations each:

```text
python no-op call       :      32 ns/call
os.getpid()             :      30 ns/call
os.write(/dev/null, 1B) :    1051 ns/call
libc getppid via ctypes :     256 ns/call
```

Read it carefully, because the interesting part is what it *doesn't* show. `os.getpid()` cost the same as a no-op Python call: it is **answered without entering the kernel** (the C library or the OS caches it), a reminder that not every library call is a system call. Writing one
byte to `/dev/null` cost about 1 µs: a genuine system call plus Python's overhead. The `ctypes` call to `getppid` costs 256 ns, mostly foreign-function overhead. The conclusions I'm confident of: crossing into the kernel costs hundreds of nanoseconds or more per call compared with tens for a plain function
call, so programs that issue a tiny `write` per byte (instead of buffering) are slow; stdio and Python file objects buffer for exactly this reason. I'm *not* claiming a Linux figure.

## Lazy allocation (run)

Asking for memory doesn't give you memory. I mapped 512 MiB of anonymous memory with `mmap` and watched the process's peak resident set size (RSS):

```text
peak RSS before mmap: 17 MB | after mmap(512MB): 17 MB | after touching 128MB: 145 MB
```

Mapping 512 MiB changed nothing; **only the pages I touched (128 MiB, one byte every page) became resident**, and the RSS rose by about 128 MB. The kernel records the *mapping* (virtual address space) and allocates physical pages on first access via a **page fault**. This is why a program can "allocate" far more than the machine
has, and why the real danger shows up later as the OOM killer (Lesson 02). The page size on this Mac was 16,384 bytes (`os.sysconf('SC_PAGE_SIZE')`); typical x86-64 Linux uses 4,096.

## fork is cheaper than it looks (run)

```text
fork of a process holding a 200 MB bytearray: 6.2 ms
```

`fork` didn't copy 200 MB in 6 ms: it duplicated the page tables and marked pages **copy-on-write**, so parent and child share physical memory until one writes to a page (then that page alone is copied). That is why shells can spawn processes cheaply and why Redis-style
snapshotting with `fork` works, and why a forked child's memory *appears* to double in some tools but isn't real. Time depends on page-table size (so a process with a lot of mapped memory forks slower).

## Buffering and fsync

A `write()` returns when the data is in the kernel's page cache, not when it is on disk. Durability requires `fsync(fd)`. I timed 20 writes of 4 KB: 1.33 ms without `fsync`, 5.25 ms with one `fsync` at the end in one trial, and 2.01 ms when `fsync` followed every write in another. That ordering (the more frequent-sync run
being faster than the single-sync run) is **noise plus macOS behaviour**: on macOS, plain `fsync` does not force the drive's cache to flush (that needs `F_FULLFSYNC`), and I only ran each case once, so I draw no conclusion about relative cost. What *is* reliable: durable writes need `fsync`, and on Linux they're the dominant cost in databases (Lesson 05).

## Reading a program with strace: a worked method (not run)

1. Start with `strace -f -e trace=execve,openat,connect,write -o t.txt cmd` and look at failures: `grep -E "= -1 " t.txt`.
2. For "hangs", attach and look at the last call: a process stuck in `futex` is waiting on a lock, in `read`/`poll` on I/O or a socket, in `wait4` on a child.
3. For "slow", `strace -c` or `-T` to find the call that takes the time (often `connect`, `getaddrinfo`-related socket calls, `fsync`).
4. Use `ltrace` for library calls and `perf trace` for lower overhead tracing on production systems (strace slows the target significantly because it stops it at every call).

Security tools build on the same boundary: **seccomp** filters which syscalls a process may make (container runtimes and systemd's `SystemCallFilter=`, Level 2 · 02), and `auditd` can log selected syscalls (Level 4 · 08).

## How It Actually Works

On entry to the kernel the CPU switches privilege level and jumps to the kernel's syscall entry point, which saves user registers, looks up the call number in a table, and dispatches to the handler, e.g. `sys_openat`. Arguments that are pointers are copied across the boundary with checks (`copy_from_user`), because user memory can't be trusted. The handler may
sleep (waiting for disk or a lock), in which case the scheduler runs something else (Lesson 04). On return the kernel restores registers and drops back to user mode. `strace` uses the `ptrace` mechanism: the kernel stops the traced process at each syscall entry and exit and lets the tracer read its registers and memory, which is why it is slow and why you can't strace a process
that is already being traced. The **vDSO** (a small kernel-provided library mapped into every process) serves very hot read-only calls like `gettimeofday`/`clock_gettime` without a real syscall, the same idea as the cached `getpid` in the measurement.

## Common mistakes

- **Reading source or docs instead of tracing** when behaviour is surprising.
- **Assuming a library call equals a system call** (and the reverse).
- **Unbuffered tiny writes** or reads in a loop.
- **Assuming `write` means durable.**
- **Straceing a latency-sensitive production process** without considering the slowdown.
- **Ignoring errno names** and googling the human text.
- **Believing memory is "used" because it was allocated** (or "free" because it wasn't touched).

## Exercise

1. On Linux, `strace -f -e trace=openat,execve` a command such as `python3 -c 'import json'` and list every path it tried before succeeding.
2. Write a C or Python program that writes 1,000,000 bytes one at a time with `os.write` versus one `os.write` of the whole buffer; time both, then explain with `strace -c`.
3. Reproduce the mmap experiment on Linux with `/proc/self/status` (`VmRSS`) before and after touching pages. Add `MAP_POPULATE` and explain the difference.
4. Use `strace -T` on a `curl` to a hostname that doesn't resolve and find which call took the time.
