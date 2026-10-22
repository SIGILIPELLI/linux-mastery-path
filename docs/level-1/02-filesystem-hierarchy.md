---
description: "The Linux directory tree and why it is laid out that way, device files, file descriptors and redirection order, with macOS comparisons run."
---

# 02 · The Filesystem Hierarchy & Everything Is a File

A Linux system has one directory tree rooted at `/`. Disks, partitions, network shares and even kernel data show up as places in that
single tree. The layout isn't arbitrary: it follows a convention so that tools, packages and administrators know where to look.
The other half of this lesson is the Unix idea that **devices, pipes, sockets and kernel data are accessed as files**, which is what
makes shell redirection and `/proc` possible.

!!! note "What was run"
    The tree below is described from the Linux `hier(7)` man page (man7.org, read October 2026) and not run. The commands in the
    "macOS comparison" sections were **run on macOS (Darwin)** and are labelled so; the point of the comparison is to show which
    ideas are universal Unix and which are Linux-specific. See Lesson 01 for the full note.

## The standard directories

| Path | Purpose (per `hier(7)` and common practice) |
|---|---|
| `/bin`, `/sbin`, `/lib` | Essential programs and libraries needed to boot and repair the system. On most modern distributions these are symlinks into `/usr` |
| `/usr` | The bulk of installed software: `/usr/bin`, `/usr/lib`, `/usr/share` (architecture-independent data), `/usr/local` for software you install by hand |
| `/etc` | Machine-local **configuration** files (text, by convention) |
| `/var` | **Variable** data that changes while the system runs: logs (`/var/log`), caches, spools, package databases, databases |
| `/home` | Users' home directories; `/root` is the superuser's home |
| `/tmp` | Temporary files; often cleared at boot, and world-writable with the sticky bit (Lesson 04) |
| `/dev` | Device files |
| `/proc`, `/sys` | Virtual filesystems exposing kernel and process information (Level 3 · 03) |
| `/boot` | Kernel and bootloader files |
| `/mnt`, `/media` | Conventional mount points for temporary and removable filesystems |
| `/opt` | Self-contained add-on software packages |
| `/run` | Runtime state since boot (PID files, sockets), usually a memory-backed filesystem |
| `/srv` | Data served by this machine (web content, FTP) |
| `/lost+found` | Where `fsck` puts recovered fragments on ext filesystems |

Why separate `/etc`, `/var` and `/usr`? Because they have different lifecycles. `/usr` can be read-only and identical across many
machines; `/etc` is small, precious and should be in version control and backed up; `/var` grows and can fill the disk. Many sites put
`/var` or `/var/log` on their own filesystem so a runaway log can't take down the root filesystem, a real operational concern
(Level 4 · 06).

### macOS comparison (run)

`ls /` on the Mac used for this course printed:

```text
Applications Library System Users Volumes bin cores dev etc home opt pkg private sbin tmp usr var
```

Shared with Linux: `bin`, `dev`, `etc`, `home`, `opt`, `sbin`, `tmp`, `usr`, `var`. Mac-specific: `Applications`, `Library`, `System`,
`Users` (macOS keeps homes in `/Users`, not `/home`). And `etc`, `tmp` and `var` are symlinks to `private/etc`, `private/tmp` and
`private/var`:

```text
lrwxr-xr-x  private/etc -> /etc   (as printed by ls -ld, trimmed)
```

and `ls /proc` fails with `No such file or directory`: **macOS has no `/proc`**, so everything in Level 3 that reads `/proc` can't be run on a Mac.

## Everything is a file (or acts like one)

The kernel exposes many things through the file interface (`open`, `read`, `write`, `close`):

| Type (first character of `ls -l`) | Example | Meaning |
|---|---|---|
| `-` | `/etc/hosts` | Regular file |
| `d` | `/usr` | Directory |
| `l` | `/bin` → `usr/bin` | Symbolic link |
| `c` | `/dev/null`, `/dev/tty` | Character device (byte stream) |
| `b` | `/dev/sda` | Block device (random access, e.g. a disk) |
| `p` | A named pipe | FIFO |
| `s` | A Unix domain socket | Local inter-process socket |

Character devices on macOS (run):

```text
crw-rw-rw-  /dev/null    crw-rw-rw-  /dev/zero    crw-rw-rw-  /dev/random    crw-rw-rw-  /dev/tty
```

The leading `c` marks a character device. Some special files you will use constantly:

- `/dev/null` discards everything written to it and reads as empty. `echo hi > /dev/null` produced no output.
- `/dev/zero` reads as an endless stream of zero bytes: `head -c 8 /dev/zero | od -An -tx1` printed eight `00` bytes.
- `/dev/urandom` and `/dev/random` supply random bytes: `head -c 4 /dev/urandom | wc -c` reported `4`.
- `/dev/tty` is your controlling terminal.

On Linux, `/proc/<pid>/...` and `/sys/...` present kernel data as files you can `cat`. Reading `/proc/meminfo` runs kernel code that
formats text on the fly; nothing is stored on disk (Level 3 · 03; not run here).

## File descriptors and redirection

Every process starts with three open **file descriptors**: `0` standard input, `1` standard output, `2` standard error. A descriptor is a small
integer indexing the process's table of open files, and redirection is just rewiring those entries before a program starts:

```bash
cmd > out.txt          # fd 1 -> out.txt
cmd 2> err.txt         # fd 2 -> err.txt
cmd > out.txt 2>&1     # fd 1 -> out.txt, THEN fd 2 -> wherever fd 1 now points (the file)
cmd 2>&1 > out.txt     # fd 2 -> where fd 1 pointed at that moment (the terminal/pipe), THEN fd 1 -> file
cmd < in.txt           # fd 0 <- in.txt
```

**Order matters**, because `2>&1` means "make fd 2 a copy of fd 1 *as it is right now*". A test (run, macOS) with
`ls /nonexistent`, which writes an error to stderr:

```text
ls /nonexistent > o.txt 2>&1        ->  error text ended up in o.txt            (1 line)
ls /nonexistent 2>&1 > o2.txt | wc  ->  error went down the pipe (1 line), o2.txt was empty (0 lines)
```

In the second form stderr was duplicated onto the pipe first, then stdout was redirected to the file, so the error went to the pipe. The
same fd numbers appear as `/dev/fd/0`, `/dev/fd/1` and `/dev/fd/2` (listing `/dev/fd` on the Mac showed `0 1 2` among others); on Linux the
equivalent view is `/proc/self/fd`.

## Mounting: how separate disks join the one tree

A filesystem on a device becomes part of the tree when it is **mounted** onto a directory (the mount point).

```bash
mount /dev/sdb1 /mnt/data      # attach (Linux; not run)
findmnt                        # tree view of mounts (Linux; not run)
umount /mnt/data
```

Anything that was in `/mnt/data` before the mount becomes hidden until unmount. Run on the Mac, `mount | head -2` printed
`/dev/disk3s1s1 on / (apfs, sealed, local, read-only, journaled)` and `devfs on /dev (devfs, ...)`: the root volume is read-only and
sealed on modern macOS, while `/dev` is a special filesystem. Persistent mounts on Linux are listed in `/etc/fstab`, or generated
as systemd mount units (Level 2 · 04).

## How It Actually Works

Path lookup is done by the kernel's **Virtual File System (VFS)** layer. To resolve `/var/log/syslog`, it starts at the root directory entry,
looks up `var` in it, then `log` in that, then `syslog`, crossing mount points when a directory is a mount point (switching to
the mounted filesystem's own root). The VFS presents the same operations (`open`, `read`, `stat`) whatever the backing filesystem
is: ext4, XFS, Btrfs, NFS, or a virtual one like procfs. That uniform interface is why `cat` works on a file, a device or `/proc/cpuinfo`,
and why `>` can target `/dev/null`. File **descriptors** are indexes into a per-process table pointing at kernel "open file" objects, so
`dup2(fd1, fd2)`, the system call that implements `2>&1`, simply makes two table entries point at the same open file.

## Common mistakes

- **Putting configuration in `/usr`** or program data in `/etc`. Follow the convention so backups and packages work.
- **`cmd 2>&1 > file`** when you meant both streams to go to the file.
- **Filling `/var` or `/tmp`** on a small root filesystem and taking the system down.
- **Hand-editing files under `/proc` or `/sys`** without knowing the effect; many writes take effect immediately.
- **Expecting `/proc` or GNU behaviour on macOS** (or the reverse).
- **Mounting over a non-empty directory** and wondering where the files went.

## Exercise

1. On Linux, run `ls -l / | head -20` and identify which top-level entries are symlinks. Compare with the table.
2. Predict the result of `ls /nonexistent /etc/hosts > out 2>&1` versus `ls /nonexistent /etc/hosts 2>&1 > out`, then run both and
   check what is in `out` and what is printed.
3. Run `df -h` and `findmnt` (or `mount`) and draw the mount tree of your machine. Which directory is on its own filesystem?
4. Use `head -c 1M /dev/zero > big` and `ls -l big` to create a file, then `rm` it. Why is `/dev/zero` better than `yes` for this?
