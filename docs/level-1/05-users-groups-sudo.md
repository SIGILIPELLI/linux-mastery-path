---
description: "Users, groups and UIDs, the passwd/shadow/group files, su vs sudo, safe sudoers rules and service accounts, with macOS runs."
---

# 05 · Users, Groups & sudo

Linux identifies people and programs by numbers: a **user ID (UID)** and **group IDs (GIDs)**. Names are a convenience layered on top. Every
permission decision from Lesson 04 uses these numbers, and `sudo` is the controlled way to borrow root's.

!!! note "What was run"
    `id`, `whoami`, `umask` and `ls` on `/etc` files were **run on macOS**, whose user database works differently from Linux's
    (macOS keeps accounts in Directory Services, so `/etc/passwd` there is nearly empty). The `/etc/passwd`, `/etc/shadow`, `useradd` and
    `visudo` details are from the Linux man pages and **not run** here. See Lesson 01.

## Identity basics

```text
$ id          (run on macOS, trimmed)
uid=501(bhanuja) gid=20(staff) groups=...
$ id -u       501
$ id -un      bhanuja
```

- **UID 0 is root**: the kernel's checks key on the number 0, not the name.
- Ordinary users usually start at UID 1000 on Linux distributions (macOS starts at 501, as seen above); system accounts (daemons) use low
  numbers and have no login shell.
- A user has one **primary group** (the GID of new files) and any number of **supplementary groups**.

## The account files (Linux)

| File | Contents | Readable by |
|---|---|---|
| `/etc/passwd` | `name:x:UID:GID:comment:home:shell` | Everyone (no passwords inside, despite the name) |
| `/etc/shadow` | `name:hash:last-change:...` password hashes and aging | root only |
| `/etc/group` | `group:x:GID:member1,member2` | Everyone |

A line looks like `alice:x:1001:1001:Alice,,,:/home/alice:/bin/bash`. The `x` means "the hash is in `/etc/shadow`". A shell of `/usr/sbin/nologin`
(or `/bin/false`) marks an account that can't log in interactively. On the Mac, `head -3 /etc/passwd` printed only comment lines (`## User Database`): the real accounts live
in a directory service, a clear sign that you can't `grep /etc/passwd` portably. Use `getent passwd alice` on Linux, which also consults LDAP/SSSD.

Managing accounts on Linux (not run):

```bash
sudo useradd -m -s /bin/bash -G sudo,docker alice     # create with home, shell, extra groups
sudo passwd alice                                     # set password
sudo usermod -aG devs alice                           # ADD to a group (-a is essential)
sudo userdel -r alice                                 # delete, and the home directory with -r
sudo chage -l alice                                   # password aging
```

`usermod -G devs alice` **without `-a`** *replaces* all supplementary groups: a classic way to remove someone from `sudo` by accident. Group changes
don't affect already-running sessions; the user must log in again (or use `newgrp`).

## su and sudo

`su` switches to another user by that user's password. `sudo` runs **one command** as another user (root by default) after authenticating
the *caller* and checking `/etc/sudoers`. Its advantages: no shared root password, per-command audit logs, fine-grained policy.

```bash
sudo systemctl restart nginx      # one command as root
sudo -u postgres psql             # as a specific user
sudo -l                           # list what I may run
sudo -i                           # root login shell (avoid; prefer single commands)
```

Edit policy only with `visudo` (it validates syntax before saving; a broken sudoers file can lock you out of root):

```text
# /etc/sudoers.d/deploy        (one file per purpose, mode 0440)
deploy ALL=(root) NOPASSWD: /usr/bin/systemctl restart myapp, /usr/bin/systemctl status myapp
%ops   ALL=(ALL:ALL) ALL
```

The syntax is `who where=(as_whom) what`. Prefer **specific commands with full paths** over `ALL`; never `NOPASSWD: ALL` for humans; beware allowing editors, shells or `tar`/`find`
(which can spawn shells and so grant full root). I confirmed on the Mac that `/etc/sudoers` is mode `-r--r-----` owned by root, and that `/usr/bin/sudo`
is setuid root (`-r-s--x--x`), the same arrangement Linux uses (Lesson 04). Sudo output is logged: via the authentication log (`/var/log/auth.log` on Debian-family, `/var/log/secure` on RHEL-family, or the journal).

## System accounts and service users

Run each service as its **own unprivileged user** (`www-data`, `postgres`, or a dedicated `myapp`) with a home of its own directory and `nologin` shell. Then a compromise of
that service gets only that user's access. systemd can create such users on the fly (`DynamicUser=yes`, Level 2 · 02).

## How It Actually Works

When a process is created it inherits its parent's credentials: real/effective UID, GID and the supplementary group list. Login programs authenticate
(PAM) and then call `setgid`, `initgroups` and `setuid` to drop from root to the user, then `exec` the user's shell, so that every descendant carries those
IDs. The kernel never sees user *names*; `ls -l` calls the C library (NSS) to translate numbers to names via `/etc/passwd`, LDAP or other sources, which is why a file can show a
number (`1001`) instead of a name on a machine that lacks that account, and why restoring files onto a system with different UID assignments gives them "wrong"
owners. `sudo` is a setuid-root program: it starts as root (effective UID), consults its policy, authenticates you via PAM, and `exec`s your command with the target credentials.

## Common mistakes

- **`usermod -G` without `-a`.**
- **Editing `/etc/sudoers` directly** instead of `visudo`/`sudoers.d`.
- **Running services as root** "to avoid permission problems".
- **`sudo` with shell redirection:** `sudo echo x > /etc/f` opens the file as *you*, not root. Use `echo x | sudo tee /etc/f`.
- **Reusing UIDs** after deleting users, so old files silently belong to a new person.
- **Assuming `/etc/passwd` lists all users** (LDAP/SSSD, and macOS).
- **Sharing one account** among people, which destroys the audit trail.

## Exercise

1. On Linux, create a user `demo` with `useradd`, add it to a new group `ops` with `usermod -aG`, and show with `id demo` that you did not drop its other groups.
2. Write a sudoers drop-in letting group `ops` restart one service and nothing else; validate with `visudo -cf`.
3. Show why `sudo echo hi > /root/x` fails for a normal user while `echo hi | sudo tee /root/x` works.
4. List the accounts on your system with a login shell (`getent passwd | awk -F: '$7 !~ /nologin|false/'`) and justify each.
