---
description: "Unix permissions end to end: rwx bits, chmod, umask, setuid/setgid/sticky, directory execute and ACLs, with runs on macOS."
---

# 04 · Permissions, umask, setuid & ACLs

Every file has an owner, a group and nine permission bits. That tiny model governs who can read your logs, run your scripts, and write into shared
directories, and nearly every "Permission denied" you will ever see. The details that trip people up are directories, `umask`, and the three
special bits.

!!! note "What was run"
    The `chmod`, `umask`, `ls` and `cat` experiments were **run on macOS** (BSD tools; the permission model is the same POSIX model Linux
    uses). ACL commands (`getfacl`/`setfacl`) and SELinux/AppArmor behaviour are Linux-specific and not run. See Lesson 01.

## Reading `ls -l`

```text
-rwxr-x---  1 alice devs  1204 Oct 21 10:00 deploy.sh
│└┬┘└┬┘└┬┘
│ │  │  └─ others:  --- (none)
│ │  └──── group:   r-x (read, execute)
│ └─────── owner:   rwx
└───────── type:    - regular file
```

For files: `r` read the content, `w` modify the content, `x` execute it as a program. For **directories** (the part that surprises people):

| Bit | On a directory means |
|---|---|
| `r` | List the names inside (`ls`) |
| `w` | Create, rename or delete entries inside (needs `x` too) |
| `x` | "Search": traverse into it and access entries by name |

So deleting a file requires `w` on the **directory**, not on the file. A test (run): `mkdir noexec; echo hi > noexec/f; chmod a-x noexec; cat noexec/f` printed
`cat: noexec/f: Permission denied`. The file itself was readable, but without `x` on its directory the path couldn't be resolved. Every
directory on the path to a file needs `x`.

The permission check uses **the first matching class only**: if you're the owner, the owner bits apply (even if the group bits would allow more).
Root bypasses the read/write checks (with exceptions such as `x` on files with no execute bit anywhere).

## chmod: symbolic and octal

Each class's bits form an octal digit: `r`=4, `w`=2, `x`=1.

```bash
chmod 640 f         # rw- r-- ---
chmod u+x,g-r f     # symbolic: add execute for owner, remove read for group
chmod -R g+rwX dir  # capital X: execute only for directories and files already executable
```

Run result: `chmod 640 f022; chmod u+x,g-r f022` gave `-rwx------`. Prefer symbolic edits when changing one bit, octal when stating the whole mode.
Capital `X` is the safe way to open a tree recursively without marking every data file executable.

## umask: default permissions for new files

New files are created with mode `0666` and directories `0777`, **minus** the bits set in the process's `umask`. Typical `umask 022` yields
`0644` files and `0755` directories. Run on macOS with two masks:

```text
(umask 022; touch f022; mkdir d022)  ->  -rw-r--r--  f022    drwxr-xr-x  d022
(umask 077; touch f077; mkdir d077)  ->  -rw-------  f077    drwx------  d077
```

`umask` prints `022` in the default shell here. Remember it's a **mask of bits to remove**, not a mode to set; and that it's per-process, inherited from the parent, so
a daemon started by systemd or a cron job may have a different umask than your login shell.

## Special bits

| Bit | Octal | On a file | On a directory |
|---|---|---|---|
| **setuid** | 4000 | Program runs with the **file owner's** identity (`passwd`, `sudo`) | Ignored on Linux |
| **setgid** | 2000 | Program runs with the file's group | New files inherit the **directory's group** (shared project directories) |
| **sticky** | 1000 | (obsolete) | Only a file's owner (or the directory owner or root) can delete/rename entries: `/tmp` |

Run results: `chmod 4755 f` gave `-rwsr-xr-x` (the `s` replaces owner `x`); `chmod 1777 d` gave `drwxrwxrwt` (the `t`); `chmod 2755 d` gave `drwxr-sr-x`.
On the Mac, `ls -l /usr/bin/sudo` shows `-r-s--x--x root wheel`: setuid root, which is how an unprivileged user's `sudo` can act as root. A **capital**
`S` or `T` means the special bit is set but the underlying `x` is not, usually a mistake.

Setuid programs are a classic attack surface: bugs in them are privilege escalations. Audit them (`find / -perm -4000 -type f 2>/dev/null`) and never set the bit on
scripts (most kernels ignore it; shell scripts are unsafe to setuid anyway).

## ACLs

When owner/group/other is too coarse (give one extra user read access), POSIX ACLs add per-user and per-group entries:

```bash
setfacl -m u:alice:r-- report.txt     # Linux (not run)
getfacl report.txt                     # shows user:alice:r--, mask::r--
setfacl -d -m g:devs:rwx shared/      # default ACL: inherited by new files
```

A `+` at the end of the mode string in `ls -l` means an ACL exists. ACLs add an **effective-rights mask**, so a restrictive group-bit `chmod` can silently reduce
what ACL entries grant. They require filesystem support (ext4 and XFS have it) and tools to preserve them (`cp -a`, `rsync -A`, `tar --acls`). macOS has its
own ACL system (`chmod +a`), a reminder that these tools aren't portable.

## How It Actually Works

The permission check happens in the kernel on `open`, `exec`, `unlink`, and others. The kernel compares the calling process's **effective UID and
supplementary group IDs** with the inode's owner, group and mode: if the UID matches the owner it uses the owner bits; otherwise if any of the process's groups matches the file's
group it uses the group bits; otherwise the other bits. Processes carry credentials (real, effective, saved IDs) that `execve` of a
setuid file changes: the *effective* UID becomes the file's owner, which is the whole mechanism of setuid. `chmod` only edits the mode field in the inode, so it is instant even on huge trees only in
the sense of per-file cost; `chmod -R` visits each inode. Linux **capabilities** (Level 3 · 07) split root's powers into pieces so programs can have just
one (like binding low ports) instead of full setuid root.

## Common mistakes

- **`chmod 777` as a fix.** It hides the real problem (wrong owner, missing directory `x`) and opens the file to everyone.
- **Forgetting directory `x`** in a path.
- **Recursive `chmod` that makes data files executable**; use `X`.
- **Misreading umask** as the mode.
- **Setuid scripts** or leaving unneeded setuid binaries.
- **Losing ACLs** when copying with plain `cp` or `tar`.
- **Expecting group changes to apply to logged-in sessions**; supplementary groups are read at login.

## Exercise

1. Predict the mode of a new file and new directory under `umask 027`, then verify.
2. Create a shared directory where members of group `devs` can create files that all `devs` can edit (hint: setgid directory + umask 002 or default ACL). Test with two users on Linux.
3. Make a file readable but a directory unlistable, and show you can still `cat dir/file` if you know the name. Explain why.
4. Run the setuid audit command on a Linux system and justify every result you find.
