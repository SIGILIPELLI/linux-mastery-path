---
description: "The Linux permission model: UIDs/GIDs, rwx on files vs directories, umask, and why a directory's execute bit means something different."
---

# 05 · Users, Groups & the Permission Model

`rwxr-xr-x` is one of the first things every new Linux user memorizes without necessarily understanding, and the
gap between memorizing and understanding shows up the first time someone has execute permission on a directory but
can't list its contents, or read permission on a file but can't open it in an editor they expect to work.

## UIDs, GIDs and the three permission classes

Every process and every file is tagged with a **UID** (user ID) and one primary **GID** (group ID), plus — for a
user — any number of *supplementary* groups. The kernel doesn't actually know usernames like `alice`; `/etc/passwd`
and `/etc/group` are just lookup tables mapping numbers to names for humans' benefit, and everything the kernel
checks is numeric. You can see this directly: delete a user from `/etc/passwd` while their UID still owns files, and
`ls -l` will print the bare number instead of a name, because the mapping is gone but the ownership tag on disk
never changed.

Permissions are checked against three classes relative to the *process* making the request, not the file: **owner**
(does the process's UID match the file's owner UID?), **group** (does any of the process's GIDs match the file's
group?), and **other** (neither of the above). The kernel checks these in that exact order and stops at the first
match — which has a real, sometimes-surprising consequence: if you own a file but your *group* permissions happen
to be more restrictive than "other," you still get the **owner** row's permissions, not whichever row is most
generous.

## Worked example: rwx means something different on directories

```text
$ mkdir project && echo "secret content" > project/notes.txt
$ chmod 750 project
$ ls -ld project
drwxr-x--- 2 vinodkumarsigilipelli vinodkumarsigilipelli 60 Oct 22 23:31 project

$ ls project
notes.txt

$ chmod 311 project
$ ls -ld project
d-wx--x--x 2 vinodkumarsigilipelli vinodkumarsigilipelli 60 Oct 22 23:31 project

$ ls project
ls: cannot open directory 'project': Permission denied

$ cat project/notes.txt
secret content
```

(Real output from this course's lab VM, run as the directory's own owner throughout — there is no root bypass
here.) At `750` (owner `rwx`, group `r-x`, other nothing), the owner can both list and traverse — unsurprising,
since the owner's bits grant everything. The genuinely sharp case is `311` (`-wx--x--x`): **no class has the read
bit**, not even the owner, so `ls project` fails for everyone, including the file's own owner — read permission on
a directory is what lets `getdents()` (what `ls`/`readdir()` use) enumerate the names inside it, and losing it
blocks that regardless of who you are. And yet `cat project/notes.txt`, naming the file directly rather than
asking the directory to list its contents, **succeeds** — because reading a file's *content* is governed by that
file's own permission bits, not its parent directory's, and the directory's execute bit alone is enough to resolve
a known path *through* it. (Note that a tool like `find project -name notes.txt` would **not** work here — `find`
has to enumerate the directory's entries to search by name, which needs the same read bit `ls` was missing; only a
path you already know by name, typed directly, skips the enumeration step.)

## How It Actually Works

The reason `r` and `x` mean such different things on a directory than on a regular file traces back to what a
directory's content actually *is*: a list of (filename, inode-number) pairs (Lesson 4). **Read** permission on a
directory lets a process call `getdents()` (what `readdir()`/`ls` ultimately use) and see that list. **Execute**
permission on a directory is really "search" permission: it lets the kernel resolve a *specific* filename inside
that directory into an inode, as one step of resolving a longer path like `/home/vinod/project/notes.txt`. These
are genuinely independent capabilities — "see what's here" versus "look something specific up by name" — and the
`311` example above is the clean demonstration: without read, `ls` has nothing to enumerate; without needing to
enumerate, knowing the name and having execute/search permission on every directory in the path is enough to reach
the file, whose own permission bits then decide whether you can actually read it.

`umask` is the other half of the model people memorize without internalizing: it's not a permission itself but a
**mask** — a bitmask of permissions to strip from whatever a program *requests* when creating a new file. A typical
default `umask` of `022` strips the group and other write bits: a program that calls `open()` asking for `0666`
(read/write for everyone, the traditional default for new files) ends up with `0644` once the umask is applied,
because `022` subtracted the write bits from group and other. This is why new files and new directories you create
interactively usually come out `644`/`755` without you ever running `chmod` — the shell's inherited `umask` is
doing it silently, and changing `umask` (in `~/.bashrc` or system-wide in `/etc/login.defs`) changes the default for
every file created afterward, not retroactively.

## Common mistakes

- **Running `chmod -R 777` to "fix" a permission problem.** This doesn't just overshoot — it removes the execute
  bit's actual meaning on files (giving every file "execute" regardless of whether it's a script) and opens every
  file and directory to world write, which on a shared or internet-facing system is a real security hole, not just
  an untidiness.
- **Confusing "I own the file" with "I have the most permissive applicable bits."** As shown above, the kernel
  checks owner/group/other in order and stops at the first match — a file you own but whose owner-bits are `r--`
  will be read-only *for you* even if "other" on that same file happens to be `rwx`.
- **Forgetting that execute-without-read on a directory is a legitimate, intentional pattern** (sometimes called a
  "blind" directory) — used so a process can reach a specific, known file path without being able to enumerate
  siblings. Seeing `--x--x--x` on a directory during an audit isn't automatically a misconfiguration.

## Exercise

Create a directory containing three files. Set the directory to `rwxr-x---` and change its group to one you're not
a member of (or simulate by predicting). Predict, then verify with a second user account (or `sudo -u`) whether that
second user can: (a) list the directory, (b) read a file inside it by exact name, (c) read a file inside it by
tab-completing the name. Then check your own `umask` with `umask -S`, create a new file and a new directory, and
explain their resulting permissions from the umask value alone.
