---
description: "Diagnosing disk-full, df vs du, deleted-but-open files, sparse files, inode exhaustion and read-only remounts, with a reproduced case."
---

# 06 · Troubleshooting Disks & Filesystems

Storage faults are among the most common causes of production incidents: the disk fills, a filesystem remounts read-only, an NFS server hangs and takes processes with it. The diagnosis follows the layered picture from Level 2 · 04. This lesson gives a decision order and reproduces the most confusing case, "`df` says full but `du` can't find the files".

!!! note "What was run"
    I reproduced the df-vs-du and sparse-file cases on **macOS** with a 40 MB HFS+ disk image, so the concepts are real and the numbers are from that run; the HFS+ filesystem has different internals from ext4 and XFS (for example how inodes work). Linux-specific diagnostic commands (`dmesg`, `fsck`, `xfs_repair`, `mount -o remount`) are described from their documentation and **were not run**. See Level 1 · Lesson 01.

## Triage order

```text
1. Is it full?                 df -h            (blocks)   and   df -i  (inodes)
2. Which directory?            du -xh --max-depth=1 /var | sort -h | tail      (-x: stay on this filesystem)
3. Does df agree with du?      if not → deleted-but-open files, hidden mounts, snapshots/reserved space
4. Is the filesystem healthy?  dmesg -T | grep -iE "i/o error|ext4|xfs|remount|read-only"; mount | grep ' ro,'
5. Is the device healthy?      smartctl -a /dev/sdX; cloud volume status; RAID state (cat /proc/mdstat)
6. Is it a network mount?      mount -t nfs,nfs4 ; processes in D state (ps axo stat,pid,wchan:20,cmd | grep '^D')
```

## "df says full, du says it isn't" (reproduced)

I created a 40 MB filesystem, had a Python process write a 20 MB file to it and **keep the file open**, then deleted the file with `rm`:

```text
start:                             1472 KB used of 40920 KB
after writing 20 MB:              21952 KB used of 40920 KB      du of the mount: 20480 KB
after rm (file still open):       df: 21952 KB used   |   du: 0 KB
lsof +L1:                          Python  FD 3w  SIZE 20971520  NLINK 0     ← a deleted file, still held open
after the holder exits:            1472 KB used of 40920 KB
```

Right after `rm`, `du` reported 0 KB (no directory entry leads to the file) while `df` still reported 21,952 KB used, because **the inode and data blocks live until the last open file descriptor closes** (Level 1 · 03). `lsof +L1` lists open files whose link count is below one (that is exactly the case); the NLINK column showed 0. When the process exited, the space came back instantly. On a Linux production box the classic
culprit is a log file removed (or rotated by rename and never reopened, Level 2 · 03) while the daemon keeps writing to it. Remedies, best first: make the process reopen its log (HUP/reload); restart the process; or free the space without a restart by truncating through procfs: `: > /proc/<pid>/fd/<n>` (Linux; not run). Then fix the rotation.

Other reasons `df` and `du` disagree:

| Cause | Check |
|---|---|
| Files hidden **under a mount point** (data written to `/data` before the disk was mounted there) | `umount /data; ls /data` or bind-mount `/` elsewhere (`mount --bind / /mnt/root`) and `du /mnt/root/data` |
| **Reserved blocks** (ext4 reserves 5% for root by default) | `tune2fs -l /dev/sdX \| grep -i reserved` |
| **Snapshots**, LVM/Btrfs/ZFS snapshot space, container layers | `lvs`, `btrfs filesystem du`, `docker system df` |
| **Sparse files** (apparent size ≠ disk usage) | Next section |
| Filesystem metadata/journal | Usually small |
| Another filesystem's data counted by `du` without `-x` | Use `du -x` |

## Sparse files: apparent vs real size (reproduced)

```text
dd if=/dev/zero of=sparse.img bs=1 count=0 seek=104857600     ls -l → 104857600 bytes (apparent)     du -k → 0 KB
dd if=/dev/zero of=dense.img  bs=1m count=5                    ls -l → 5242880 bytes                   du -k → 5120 KB
```

The sparse file claims 100 MB but occupies **no blocks**, because only the region written has storage, and reading the hole returns zeros. VM disk images, database files and `truncate -s` create them. `ls -l` shows the apparent size; `du` shows what's allocated. Copying a sparse file naively (`cp` without `--sparse`, `rsync` without `-S`, many backup tools) can expand it to full size and fill the
destination. Conversely, a thin-provisioned VM disk may *grow* until the underlying storage is exhausted even though inside the VM `df` looks fine (Level 2 · 05).

## Inode exhaustion

`df -i` shows inode usage. A filesystem like ext4 creates a **fixed number of inodes at `mkfs` time**; millions of tiny files (mail queues, session files, cache directories) can exhaust inodes while plenty of blocks remain, and the error is the same "No space left on device" (`ENOSPC`). Find the culprit with `for d in /var/*; do echo "$(find $d -xdev | wc -l) $d"; done | sort -n | tail`. Fix: delete the small files
(`find dir -type f -mtime +7 -delete`, run with `-print` first), fix the application, or reformat with more inodes (`mkfs.ext4 -N`/`-i`). XFS allocates inodes dynamically, so it's far less prone to this. (HFS+ on the Mac image allocates dynamically too, so I could not reproduce exhaustion there.)

## Read-only filesystem

If the kernel detects serious filesystem or I/O errors, ext4 (with `errors=remount-ro`, the common option, Level 2 · 04) **remounts the filesystem read-only** to prevent corruption. Symptoms: "Read-only file system" errors (`EROFS`), failed writes, services crashing. Diagnose: `mount | grep ' ro,'`, `dmesg -T | grep -iE "error|remount"`. This usually indicates a failing disk,
a cloud volume incident, or an unclean shutdown. **Don't just remount read-write and carry on**; first copy important data off, check the device health, then `fsck` the unmounted filesystem (`xfs_repair` for XFS), and consider replacing the device. Take a snapshot or image before repair attempts.

## Hung network mounts

NFS with `hard` mounts (the default) retries forever when the server disappears: processes touching it enter **D state** (uninterruptible sleep) and cannot be killed (Level 1 · 07), `df` hangs, and load average climbs without CPU use (Level 3 · 04). Diagnose: `ps axo stat,pid,wchan:20,cmd | awk '$1 ~ /D/'` (wchan shows `nfs_...` waits), `dmesg | grep nfs`, `showmount`/`rpcinfo` against the server. Recovery:
restore the server/network, or `umount -f -l /mnt/nfs` (lazy detach; force) after stopping dependent processes. Prevent: `soft,timeo=..,retrans=..` options trade hangs for possible data errors (appropriate for read-only data, risky for writes), `nofail,_netdev` in fstab so boot doesn't depend on the share, and don't put critical paths such as `/var/log` on NFS. Avoid running `df` or `ls` in a loop on a suspect mount in monitoring.

## Filesystem corruption and recovery

- Always **unmount** (or boot rescue media) before `fsck`/`xfs_repair`.
- `fsck -n` (check without changing) first; `fsck -y` repairs and may delete data. Check `lost+found`.
- Prefer restoring from backup (Lesson 02) over repairing a badly damaged filesystem.
- Journals make crash recovery fast; they don't protect against failing hardware.
- For suspected bad blocks use `smartctl -t long` and consider `ddrescue` to copy what can be read from a failing disk to a good one before any repair.

## Preventing disk-full incidents

Monitor **free space and inodes** with alerts at, say, 80% and 90%, and on the *growth rate* ("full in 6 hours"); give `/var` or `/var/log` its own filesystem (Level 1 · 02) so logs can't fill root; set journald and logrotate limits (Level 2 · 03); expire caches and temp files (`systemd-tmpfiles`); keep reserved space; and alert on deleted-but-open large files (`lsof +L1`) in a periodic check.

## How It Actually Works

`df` asks the filesystem for its statistics via the `statfs` system call (total/free blocks and inodes), so it reflects the filesystem's own accounting, including deleted-but-open files. `du` walks the directory tree and sums `st_blocks` from `stat` on each name it can reach, so it sees only *named* files. Any gap between them is space the filesystem has allocated but no reachable name accounts for. A sparse
file's `st_size` (apparent) differs from `st_blocks` (allocated). When ext4 hits certain errors, its `errors=` mount option decides the response: continue, remount read-only, or panic.

## Common mistakes

- **Deleting more files** to free space when a deleted file is still open.
- **`du` without `-x`** and counting other filesystems.
- **Ignoring inodes.**
- **Remounting read-write after errors** without investigating the device.
- **`fsck` on a mounted filesystem.**
- **Copying sparse images without sparse support.**
- **Logs on NFS** or other critical paths on hang-prone mounts.
- **No alert on growth rate.**

## Exercise

1. Reproduce the deleted-but-open case on Linux with `tail -f` on a 1 GB file, then recover the space without killing `tail` using `/proc/<pid>/fd`.
2. Create a 1 GB sparse file, copy it with `cp`, `cp --sparse=always`, and `rsync -S`, and compare `du` for each.
3. On a small ext4 image, exhaust inodes (create 100,000 empty files) and capture `df -h` and `df -i`.
4. Write a check script (Lesson 01 style) that prints any deleted file larger than 100 MB still held open, and test it with a fake `lsof +L1` output.
