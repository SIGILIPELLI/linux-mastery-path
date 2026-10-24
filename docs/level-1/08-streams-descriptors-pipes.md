---
description: "File descriptors 0/1/2 as kernel-level table entries, what a pipe actually is, and why shell redirection order changes the result."
---

# 08 · Standard Streams, File Descriptors & Pipes

`command > file 2>&1` works for almost everyone almost immediately after seeing it once, and `command 2>&1 > file`
quietly does something different — redirecting stderr to the terminal, not the file — which only makes sense once
you know what a file descriptor actually is and what `>` and `2>&1` each really do to it.

## File descriptors: numbers, not files

Every open file, socket, or pipe a process has is tracked by the kernel in a small per-process table, and the
process refers to each entry by a small integer: the **file descriptor**. By convention, every process starts with
three already open: **0** (stdin), **1** (stdout), and **2** (stderr). These aren't special in any way the kernel
enforces — a program could write its normal output to fd 2 and nobody would stop it — they're a convention that
shells, terminals, and virtually all Unix tools agree to honor: read input from 0, write normal output to 1, write
errors/diagnostics to 2 so they can be told apart from the data even when both are flowing to the same terminal.

## Worked example: inspecting real file descriptors and a redirection-order gotcha

```text
$ sleep 30 < /dev/null > /tmp/fdtest/out.log 2>&1 &
$ ls -l /proc/<pid>/fd
lr-x------ 1 vinodkumarsigilipelli vinodkumarsigilipelli 64 Oct 24 16:10 0 -> /dev/null
l-wx------ 1 vinodkumarsigilipelli vinodkumarsigilipelli 64 Oct 24 16:10 1 -> /tmp/fdtest/out.log
l-wx------ 1 vinodkumarsigilipelli vinodkumarsigilipelli 64 Oct 24 16:10 2 -> /tmp/fdtest/out.log

$ ls /nonexistent > cmd.log 2>&1
$ cat cmd.log
ls: cannot access '/nonexistent': No such file or directory

$ ls /nonexistent 2>&1 > cmd2.log
ls: cannot access '/nonexistent': No such file or directory
$ cat cmd2.log
$
```

(Real output from this course's lab VM; PID substituted for readability.) The `/proc/<pid>/fd` listing is not a
metaphor — it's a literal, inspectable directory of symlinks, one per open file descriptor, showing exactly what
each number currently points at: fd 0 to `/dev/null` (because the command redirected stdin there explicitly), and
*both* fd 1 and fd 2 pointing at the same log file, because `> file 2>&1` means "point fd 1 at `file`, then point
fd 2 at whatever fd 1 is now pointing at." The two `ls /nonexistent` runs show why **order matters**: in the first,
`> cmd.log` runs first (fd 1 now points at the file), then `2>&1` makes fd 2 point there too — so the error, which
`ls` writes to fd 2, ends up in `cmd.log`. In the second, `2>&1` runs *first*, while fd 1 still points at the
original terminal — so fd 2 is pointed at the terminal, and *then* `> cmd2.log` repoints fd 1 (and only fd 1) at
the file. The error goes to fd 2, which is still the terminal, so it prints live and `cmd2.log` ends up empty.
Redirections are processed strictly left to right, each one only affecting the descriptor named at that moment —
there's no "redirect everything" shortcut hiding behind `2>&1`.

## How It Actually Works

A **pipe** (`|`) is the kernel creating an in-memory buffer with two file descriptor ends: one open for writing
(wired to the left command's stdout) and one open for reading (wired to the right command's stdin). It's not a
temporary file, and it's not line-buffered text sitting in a shell variable — it's a genuine kernel object with a
fixed-size buffer (commonly 64 KiB on Linux). This has a real, sometimes-surprising consequence: if the writing
end fills that buffer faster than the reading end drains it, the writer **blocks** — the `write()` syscall simply
doesn't return until there's room — which is how `yes | head -n1` can run `yes` (which would otherwise loop
forever generating text) and still finish almost instantly: once `head` reads one line and exits, the pipe's read
end closes, and the next time `yes` tries to write, it receives `SIGPIPE` and is killed by the kernel rather than
spinning forever into a pipe nobody is reading.

`2>&1` is implemented with the `dup2()` syscall: it doesn't make fd 2 an alias that tracks fd 1 forever, it makes
fd 2, *at that instant*, point at whatever underlying open file fd 1 currently references — after which the two
are independent again (closing one doesn't affect the other, and later redirecting fd 1 again doesn't move fd 2).
That one-time-copy semantic, more than anything else, is what makes redirection order something you have to reason
about left-to-right rather than treat as a single declarative block.

## Common mistakes

- **Writing `2>&1 > file` when you meant `> file 2>&1`.** As shown above, these are not equivalent, and the bug is
  silent — the command still runs, output still appears somewhere, just not all in the file you expected.
- **Treating a pipe as having unlimited buffering.** A producer that writes much faster than a slow consumer reads
  will block on `write()` once the kernel pipe buffer fills — this is normal, correct backpressure, not a hang,
  but it surprises people debugging a "stuck" process that's actually just waiting for a slow reader downstream.
- **Assuming closing a shell variable or unsetting something closes a file descriptor.** Descriptors are closed by
  explicit `close()` calls (or a process exiting, or `exec` without the `close-on-exec` flag being overridden) —
  they are kernel table entries, not shell-level state, which is exactly why `/proc/<pid>/fd` can inspect them from
  outside the process entirely.

## Exercise

Start any long-running command in the background (`sleep 120 &`), find its PID with `$!`, and inspect
`/proc/<pid>/fd` to see its open descriptors. Then predict, then verify, the difference between
`command > out.log 2>&1` and `command 2>&1 > out.log` using a command that writes to both stdout and stderr (`ls`
on one existing and one nonexistent path works well: `ls /tmp /nonexistent`).
