---
description: "SUID, SGID and the sticky bit explained through real examples (passwd, /tmp), plus POSIX ACLs for when owner/group/other isn't enough."
---

# 06 · Advanced Permissions: SUID, SGID, Sticky Bit & ACLs

The standard `rwx` × owner/group/other model (Lesson 5) can't express "let any user run this program with the
file owner's privileges" or "let everyone create files here, but only the creator can delete their own" — both are
common, real requirements, and both are handled by three special bits plus an extension mechanism that goes beyond
the classic nine permission bits entirely.

## The three special bits

**SUID** (set-user-ID, shown as `s` in the owner's execute position) makes a program run with the **file owner's**
UID, not the invoking user's UID, for as long as that process runs. **SGID** (set-group-ID, same idea in the group
execute position) does the equivalent for the group; on a *directory* specifically, SGID means something extra:
new files created inside inherit the directory's group rather than the creating user's primary group — the
standard way to make a shared team directory where everyone's files end up in the same group automatically. The
**sticky bit** (shown as `t` in the other execute position) means something different again, and only matters on
directories: it restricts *deletion* — inside a sticky directory, you can only delete or rename files you own,
regardless of write permission on the directory itself.

## Worked example: passwd, a shared directory, and /tmp

```text
$ ls -l /usr/bin/passwd
-rwsr-xr-x 1 root root 142552 Feb  3  2026 /usr/bin/passwd

$ ls -ld /tmp
drwxrwxrwt 12 root root 240 Oct 22 23:30 /tmp

$ mkdir team-shared && chmod 2775 team-shared
$ sudo chgrp testeng team-shared
$ ls -ld team-shared
drwxrwsr-x 2 vinodkumarsigilipelli testeng 40 Oct 22 23:32 team-shared

$ id
uid=501(vinodkumarsigilipelli) gid=1000(vinodkumarsigilipelli) groups=1000(vinodkumarsigilipelli),999(systemd-journal)

$ touch team-shared/report2.txt
$ ls -l team-shared/report2.txt
-rw-rw-r-- 1 vinodkumarsigilipelli testeng 0 Oct 22 23:32 team-shared/report2.txt
```

(Real output from this course's lab VM.) `passwd` is owned by `root` and carries the SUID bit (the `s` where you'd
expect `x`) — which is *why* an unprivileged user running `passwd` can update `/etc/shadow`, a file only root can
normally write. Without SUID, every user would need root access just to change their own password, which defeats
the point of having unprivileged accounts at all; SUID lets the *program* temporarily act with elevated privilege
while still being invoked by a normal user, and the program itself is responsible for only doing the one narrow,
safe thing it was written to do (update the calling user's own password entry, nothing else). `/tmp`'s permissions
(`rwxrwxrwt`, that trailing `t`) show the sticky bit in the wild: everyone can create files in `/tmp`, but the
sticky bit stops one user from deleting another user's temp files even though the directory itself is
world-writable. `chmod 2775` on `team-shared` sets SGID (the leading `2`); `id` confirms this shell's primary group
is still `vinodkumarsigilipelli` (gid 1000) — yet the file it creates, `report2.txt`, comes out owned by group
`testeng`, the *directory's* group, not the creating process's primary group. That's SGID-on-a-directory working
exactly as specified: inheritance happens regardless of what group the creating process would otherwise have used.

## How It Actually Works

The kernel implements SUID/SGID by checking, at `execve()` time (the syscall that actually replaces a process's
code with a new program), whether the target file has the SUID or SGID bit set. If so, instead of the new process
keeping the *calling* process's real UID/GID as its *effective* UID/GID (the normal case — effective IDs are what
permission checks actually use), the kernel sets the new process's effective UID/GID to the **file's owner/group**.
The process's real UID (who actually invoked it) is preserved separately, which is how `passwd` and similar tools
can tell "who is calling me" from "what privilege do I currently have" and behave accordingly rather than blindly
trusting the elevated privilege for everything.

This mechanism is also exactly why SUID is treated as a security-sensitive feature rather than a convenience: any
bug in a SUID-root binary is a potential **privilege escalation** path, because the bug now executes with root's
effective UID regardless of who triggered it. This is why the Linux kernel, by default, **refuses to honor the SUID
bit on shell scripts** (even though you can technically `chmod u+s` one) — a script's first line only names an
interpreter, and there's a well-known race window between the kernel opening the script and the interpreter
re-opening it, during which the file on disk could be swapped out from under the privilege check; compiled binaries
don't have that two-step open. It's also why security audits specifically grep filesystems for unexpected SUID
binaries (`find / -perm -4000 -type f`) — a SUID binary that shouldn't be there, or a legitimate one with a known
vulnerable version, is one of the most direct routes from "a foothold as a normal user" to "root."

POSIX **ACLs** (`setfacl`/`getfacl`) exist for everything the owner/group/other model genuinely can't express at
all: granting one *specific* additional user (not a whole group) read access to a file, for instance, without
changing its owner or creating a new group just for that one grant. `getfacl` on a file with ACLs set shows the
extra entries, and `ls -l` signals their presence with a trailing `+` after the permission string — a detail
that's easy to miss and a common source of "why can this person read a file whose `ls -l` bits say they shouldn't
be able to" confusion during audits.

## Common mistakes

- **Setting SUID on a shell script and being confused when it "doesn't work."** As explained above, the kernel
  deliberately ignores SUID on interpreted scripts on most systems; if you need SUID behavior for a script's logic,
  the standard fix is a small compiled wrapper binary that is itself SUID and that `exec`s the script non-SUID.
- **Confusing the sticky bit with SGID.** They occupy similar-looking positions in `ls -l` output (`t` vs `s` in
  the "other" vs "group" execute slot) but do unrelated things — sticky restricts deletion, SGID affects
  group ownership inheritance (on directories) or effective GID (on executables).
- **Forgetting that `chmod -R` on a directory tree with SGID set recalculates the special bits per-file**, often
  stripping them from regular files (which don't need SGID at all) while potentially leaving directories correct —
  always re-check with `find dir -type d -perm -2000` after a bulk `chmod` if SGID inheritance matters.

## Exercise

Find every SUID and SGID binary on a Linux machine you control with `find / -perm -4000 -o -perm -2000 -type f
2>/dev/null`, pick three, and for each one explain in one sentence why it plausibly needs elevated privilege (or
flag it as suspicious if you can't justify it). Then create a shared-group directory with SGID set, have two
different users (or simulate with `sudo -u`) create files in it, and confirm both files end up in the same group
despite the users having different primary groups.
