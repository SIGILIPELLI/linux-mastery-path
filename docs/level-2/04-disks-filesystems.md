---
description: "Partitions, ext4 vs XFS, mount options, fstab with UUIDs and nofail, df vs du and inodes, with a disk-image run and a tested fstab linter."
---

# 04 · Disks, Partitions & Filesystems

A disk is a flat array of blocks. To store files you divide it into **partitions**, put a **filesystem** (ext4, XFS, Btrfs...) on each, and **mount** the filesystem into the directory tree (Level 1 · 02). Most
"my server won't boot" and "disk full" incidents live in this layer.

!!! note "What was run"
    The Linux tools here (`lsblk`, `blkid`, `fdisk`, `mkfs.ext4`, `fsck`, `/etc/fstab`) were **not run**; they're described from man pages and standard practice. What I ran on **macOS**: creating a 20 MB disk image, formatting it,
    mounting, filling and detaching it (same concepts, different tools and filesystem: Journaled HFS+), and a **Python fstab linter with 10 passing tests**. See Level 1 · Lesson 01.

## The layers

```text
physical disk / virtual disk (/dev/sda, /dev/nvme0n1, /dev/vda)
  └─ partition table (GPT or MBR)  →  partitions (/dev/sda1, /dev/nvme0n1p2)
        └─ [optional: LVM / RAID / LUKS encryption]  (Lesson 05)
              └─ filesystem (ext4, XFS, Btrfs, ...)  →  mounted at a directory
```

Device names: `sd*` (SCSI/SATA/USB), `vd*` (virtio), `nvme0n1p1` (NVMe namespace and partition), `xvd*` (Xen). **These names are assigned at detection time and can change between boots**, which is why configuration uses
UUIDs and labels instead.

Inspecting (Linux; not run):

```bash
lsblk -f                  # tree of disks, partitions, filesystems, UUIDs, mount points
blkid                     # UUID, LABEL and type of each block device
sudo fdisk -l /dev/sda    # partition table      (parted, gdisk for GPT)
findmnt                   # what's mounted where, with options
df -hT                    # free space per mounted filesystem, with type
```

## Create, format, mount (a disk image, run on macOS)

I did the macOS equivalent with a file as the "disk":

```text
hdiutil create -size 20m -fs "Journaled HFS+" -volname labdisk lab.dmg      # make and format a 20 MB image
hdiutil attach lab.dmg                                                      # it appears as a device and mounts at /Volumes/labdisk
mount | grep labdisk   →  /dev/diskNsM on /Volumes/labdisk (hfs, local, nodev, nosuid, journaled, noowners, nobrowse)
df -h /Volumes/labdisk →  size=20Mi used=992Ki avail=19Mi
```

Of that 20 MB, 992 KiB was already used by the empty filesystem's own metadata (journal, catalog): **a new filesystem is never fully empty**. `diskutil info` reported `File System Personality: Journaled HFS+`,
`Allocation Block Size: 4096 Bytes`, and a device block size of 512 bytes. I then wrote a file, detached (`ls /Volumes/labdisk` then failed: **unmounted data is not in the tree**), re-attached, and filled it with `dd if=/dev/zero of=/Volumes/labdisk/big bs=1m`
(macOS `dd` accepts lowercase `1m`; GNU `dd` wants `1M`). `dd` stopped after 18,874,368 bytes and `df` showed `capacity=96%`.

The Linux sequence for a new data disk (not run; **destructive, only on a disk you can wipe**):

```bash
sudo parted /dev/vdb --script mklabel gpt mkpart data 0% 100%      # GPT partition table + one partition
sudo mkfs.ext4 -L data /dev/vdb1                                    # or mkfs.xfs
sudo mkdir -p /data && sudo mount /dev/vdb1 /data                   # try it by hand first
blkid /dev/vdb1                                                      # copy the UUID into fstab
```

## Choosing a filesystem

| FS | Notes (general knowledge; check your distribution's defaults) |
|---|---|
| **ext4** | The long-standing Linux default: mature, journaled, can grow and shrink offline/online (grow), `fsck` support |
| **XFS** | Default on RHEL family; excels with large files and parallel I/O; can grow but **not shrink**; no boot-time fsck (`xfs_repair` manually) |
| **Btrfs** | Copy-on-write, snapshots, checksums, built-in multi-device; more operational complexity |
| **tmpfs** | RAM-backed (`/tmp`, `/run`, `/dev/shm`); contents lost at reboot |
| **NFS / CIFS** | Network filesystems; availability depends on the network and server |

A **journal** records intended metadata changes before applying them so a crash can be recovered by replaying it, rather than scanning the whole disk (ext4 and XFS both journal metadata). Journaling protects the filesystem's
*consistency*, not necessarily the latest data; applications that need durability call `fsync`.

## /etc/fstab: mounts at boot

Six fields: `device  mountpoint  type  options  dump  pass`.

```text
UUID=11111111-2222-... /      ext4  errors=remount-ro        0 1
UUID=99999999-8888-... /data  xfs   defaults,nofail,noatime  0 0
tmpfs                  /tmp   tmpfs defaults,noexec,nosuid,size=1g 0 0
nas:/export/backups    /mnt/nas nfs4 _netdev,nofail,ro       0 0
```

- **Use `UUID=` or `LABEL=`**, not `/dev/sdb1` (names change).
- **`nofail`** lets boot continue if the device is missing; without it a missing data disk drops the machine to the **emergency shell** (Lesson 01). Network mounts need `_netdev` (wait for the network) and usually `nofail`.
- **Options**: `noatime`/`relatime` (don't update access times on every read), `noexec`, `nosuid`, `nodev` (hardening for `/tmp`, uploads), `ro`, `discard` or periodic `fstrim` for SSDs.
- **`pass`**: fsck order at boot: `1` for root, `2` for others, `0` to skip (XFS must be `0`).
- Test before rebooting: `sudo mount -a` mounts everything in fstab and shows errors; `findmnt --verify` (util-linux) checks syntax. A typo in fstab is a classic way to make a server unbootable.

### A tested fstab linter (run)

```python
"""Lint /etc/fstab text for common boot-time hazards. Static checks only."""
import re, sys

def parse(text):
    rows = []
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"): continue
        f = s.split()
        rows.append((n, f))
    return rows

def lint(text):
    problems = []
    for n, f in parse(text):
        if len(f) < 4: problems.append(f"line {n}: needs at least 4 fields (device mountpoint type options), got {len(f)}"); continue
        dev, mp, fstype, opts = f[:4]
        dump = f[4] if len(f) > 4 else "0"
        passno = f[5] if len(f) > 5 else "0"
        o = set(opts.split(","))
        if re.match(r"^/dev/(sd|vd|nvme|xvd)", dev): problems.append(f"line {n}: {dev} is an unstable device name; use UUID= or LABEL= (names can change between boots)")
        if fstype in ("nfs", "nfs4", "cifs", "smb3") and not ({"nofail", "_netdev"} & o): problems.append(f"line {n}: network mount {mp} without _netdev/nofail can block or fail boot")
        if mp not in ("/", "swap", "none", "/boot", "/boot/efi", "/usr", "/var") and "nofail" not in o and fstype not in ("proc", "sysfs", "tmpfs", "devpts") and not dev.startswith(("proc", "sys", "tmpfs", "devpts")):
            problems.append(f"line {n}: {mp} is not marked nofail; if the disk is missing boot drops to emergency mode (fine for essential mounts, risky for data disks)")
        if mp == "/" and passno != "1": problems.append(f"line {n}: root filesystem should have fsck pass 1, got {passno}")
        if fstype == "xfs" and passno != "0": problems.append(f"line {n}: xfs does not use fsck at boot; pass should be 0")
        if mp in ("/tmp", "/var/tmp", "/dev/shm") and not {"noexec", "nosuid"} <= o: problems.append(f"line {n}: {mp} without noexec,nosuid (hardening)")
        if fstype == "swap" and mp != "none" and mp != "swap": problems.append(f"line {n}: swap entries conventionally use 'none' as the mount point")
        if not re.match(r"^[0-2]$", dump) or not re.match(r"^[0-2]$", passno): problems.append(f"line {n}: dump/pass fields must be 0, 1 or 2")
    mounts = [f[1] for _, f in parse(text) if len(f) >= 2]
    for m in set(mounts):
        if m not in ("none", "swap") and mounts.count(m) > 1: problems.append(f"mount point {m} appears {mounts.count(m)} times")
    return problems

if __name__ == "__main__":
    p = lint(open(sys.argv[1]).read()); print("\n".join(p) if p else "OK"); sys.exit(1 if p else 0)
```

The pytest suite (`10 passed`) checks a good fstab plus one mutation per rule. On a deliberately bad four-line file:

```text
line 1: /dev/sdb1 is an unstable device name; use UUID= or LABEL= (names can change between boots)
line 1: /srv is not marked nofail; if the disk is missing boot drops to emergency mode (fine for essential mounts, risky for data disks)
line 2: network mount /mnt/nas without _netdev/nofail can block or fail boot
line 2: /mnt/nas is not marked nofail; if the disk is missing boot drops to emergency mode (fine for essential mounts, risky for data disks)
line 3: /tmp without noexec,nosuid (hardening)
line 4: /dev/sda2 is an unstable device name; use UUID= or LABEL= (names can change between boots)
line 4: root filesystem should have fsck pass 1, got 2
```

My first version flagged `/boot` as missing `nofail`, which broke the "good" test; the fix was to exempt essential mounts (`/`, `/boot`, `/usr`, `/var`), which shows how a linter's rules embed judgment calls. It's a text check only; the
real test is `mount -a` on a disposable VM.

## "Disk full" has several causes

```bash
df -h            # blocks: which filesystem is full?
df -i            # inodes: free space but "No space left on device"? → inode exhaustion (millions of tiny files)
du -xh --max-depth=1 /var | sort -h | tail    # where is the space? (-x stays on one filesystem)
lsof +L1         # deleted-but-open files still holding space (Level 1 · 03)
```

On the macOS image, `df -i` reported 5 inodes used and ~4.29 billion free; HFS+ allocates catalog records dynamically, so inode exhaustion works differently there from ext4, which creates a **fixed number of inodes at `mkfs` time**. Other causes: a
runaway log, a journal that grew (`journalctl --vacuum-size`), Docker layers, reserved blocks (ext4 reserves 5% for root by default; `tune2fs -m`). `df` and `du` can disagree: open deleted files, mount points hiding data underneath, and sparse files all explain it.

## Resizing and checking

`resize2fs` (ext4) and `xfs_growfs` (XFS) grow a filesystem to fill an enlarged partition or LVM volume (Lesson 05). `fsck` repairs **unmounted** ext filesystems; running it on a mounted one can corrupt it. After an unclean
shutdown the journal replay usually suffices. Always have backups before repair (Level 4 · 02): `fsck` makes the filesystem consistent, not necessarily the data complete (check `lost+found`).

## How It Actually Works

The kernel's block layer exposes each device as a sequence of fixed-size blocks and queues read/write requests (Level 3 · 05). A filesystem driver turns file operations into block operations: it keeps an on-disk structure of
inodes (Level 1 · 03), a bitmap of free blocks, and a journal. `mount` tells the VFS to attach that driver's root at a directory, after which paths crossing the mount point are served by it. **Page cache** sits in between: writes first
land in memory and are flushed later, which is why a sudden power loss can lose recently written data that never reached the disk, and why `sync`, `fsync` and filesystem journaling modes matter (Level 3 · 02).

## Common mistakes

- **Using `/dev/sdX` names** in fstab.
- **A data disk or NFS mount without `nofail`** that stops boot.
- **Editing fstab and rebooting without `mount -a`.**
- **Running `fsck` on a mounted filesystem.**
- **Formatting the wrong device** (check `lsblk`, UUIDs, sizes twice).
- **Only watching block usage** and missing inode exhaustion.
- **`rm` of a huge open log** expecting space back.
- **Shrinking XFS** (impossible); plan capacity.

## Exercise

1. On a Linux VM, add a spare virtual disk, partition it, create ext4, mount it, add an fstab entry by UUID with `nofail`, and verify with `mount -a` and a reboot.
2. Create 100,000 empty files on a small ext4 image and watch `df -i`; compare with `df -h`.
3. Run the linter on your own `/etc/fstab`; justify or fix every message.
4. Explain, with the layers diagram, what happens (step by step) when you run `echo hi > /data/x` and then pull power immediately. What might be lost?
