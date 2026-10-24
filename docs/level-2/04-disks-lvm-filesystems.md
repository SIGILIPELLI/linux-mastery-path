---
description: "Partitions, LVM's physical/volume/logical-group model, and creating an ext4 filesystem on a logical volume spanning two disks."
---

# 04 · Disks & Block Devices: Partitions, LVM & Filesystems

A disk, a partition, and a filesystem are three different layers that get flattened into "my C: drive" thinking
if you've never had to grow storage past what a single physical disk gives you. LVM exists specifically to break
the assumption that a filesystem has to live on one unresizable chunk of one physical disk, and the clearest way to
understand it is to build one from nothing but a couple of plain files.

## Partitions, then LVM, on top of raw block devices

A **block device** (`/dev/vda`, `/dev/sda`, `/dev/nvme0n1`...) is the kernel's name for something that can be read
and written in fixed-size blocks — a real disk, but also, as this lesson demonstrates, a loopback-mounted plain
file. A **partition** divides one block device into fixed regions (`/dev/vda1`, `/dev/vda2`...) at creation time;
resizing later means shuffling data to make room, which is exactly the rigidity **LVM** (Logical Volume Manager)
exists to remove. LVM inserts a layer of indirection: one or more **physical volumes** (PVs — a partition or whole
disk) are pooled into a **volume group** (VG), and **logical volumes** (LVs) are carved out of that pool's *total*
space, not tied to any one underlying PV. An LV can span multiple physical disks, and growing it later is a
software operation against the VG's free space, not a disk-geometry problem.

## Worked example: building LVM across two disks from scratch

```text
$ sudo dd if=/dev/zero of=disk1.img bs=1M count=512
$ sudo dd if=/dev/zero of=disk2.img bs=1M count=512
$ LOOP1=$(sudo losetup -f --show disk1.img)
$ LOOP2=$(sudo losetup -f --show disk2.img)
$ echo "$LOOP1 $LOOP2"
/dev/loop0 /dev/loop1

$ sudo pvcreate $LOOP1 $LOOP2
  Physical volume "/dev/loop0" successfully created.
  Physical volume "/dev/loop1" successfully created.

$ sudo vgcreate demovg $LOOP1 $LOOP2
  Volume group "demovg" successfully created
$ sudo vgs
  VG     #PV #LV #SN Attr   VSize    VFree
  demovg   2   0   0 wz--n- 1016.00m 1016.00m

$ sudo lvcreate -n demolv -L 800M demovg
  Logical volume "demolv" created.

$ sudo mkfs.ext4 -q /dev/demovg/demolv
$ sudo mount /dev/demovg/demolv /mnt/demolv
$ df -h /mnt/demolv
Filesystem                 Size  Used Avail Use% Mounted on
/dev/mapper/demovg-demolv  770M  224K  714M   1% /mnt/demolv
```

(Real output from this course's lab VM — two 512 MB loopback-mounted *plain files* were made to behave exactly
like two physical disks.) `vgs` shows the pool's total usable size, `1016.00m` — slightly less than the raw
1024 MB (2×512 MB) because LVM reserves metadata space on each PV. The logical volume, `demolv`, was created at
`800M` — larger than *either individual loop device* (512 MB each), which is only possible because the VG pools
both PVs' space together; an ordinary partition could never do this. The resulting device, `/dev/mapper/demovg-
demolv`, is what gets formatted and mounted exactly like any normal block device — `mkfs.ext4` and `mount` have no
idea (and don't need to know) that the space underneath is actually spread across two separate files.

## How It Actually Works

LVM is implemented on top of the kernel's **device-mapper** framework: `/dev/mapper/demovg-demolv` is not a
"real" block device backed by one contiguous span of disk — it's a virtual device whose I/O requests the kernel
remaps, according to a mapping table `lvcreate` wrote, onto specific extents on the underlying physical volumes.
This is the same device-mapper machinery that implements LVM snapshots (copy-on-write extent tracking), disk
encryption (`dm-crypt`, which Level 3's namespaces-and-security material touches indirectly), and software RAID
(`dm-raid`) — LVM is one consumer of a general-purpose block-remapping layer, not a special case bolted directly
into the filesystem code.

The filesystem (`ext4` here) sits entirely above this and is, by design, unaware of any of it: `mkfs.ext4` just
sees a block device of a given size and lays out its own structures (superblock, inode tables, block groups) onto
it, exactly as it would onto a plain partition. This separation of concerns — device-mapper handles "where do
these logical blocks actually live," the filesystem handles "how are files organized within this block range" — is
what makes LVM snapshots, online resizing (`lvextend` followed by `resize2fs` or `xfs_growfs`), and moving a live
logical volume between physical disks (`pvmove`) all possible without the filesystem driver needing to know
anything changed underneath it, beyond a resize notification.

## Common mistakes

- **Resizing the logical volume and forgetting to resize the filesystem on top of it.** `lvextend` only changes
  how much block space the LV occupies; the filesystem still thinks it's the old size until you also run
  `resize2fs` (ext4) or `xfs_growfs` (XFS, which only grows, never shrinks) — a very common "I grew my disk but
  `df` still shows the old size" support question.
- **Removing a physical volume that still has extents in use.** `vgreduce`/`pvremove` on a PV that's still backing
  live data will fail safely (LVM checks this), but assuming you can freely detach any PV from a VG without first
  migrating its data (`pvmove`) is a common and avoidable mistake.
- **Confusing "online" resize capability with filesystem shrink capability.** Most filesystems can be *grown*
  online without unmounting; *shrinking* is far more restrictive (ext4 can shrink but usually needs to be
  unmounted first; XFS cannot shrink at all) — plan storage layouts assuming shrinking will be hard or impossible.

## Exercise

Repeat this lesson's loopback LVM setup yourself (it's entirely safe — nothing touches real disks), then grow the
logical volume with `lvextend -L +200M demovg/demolv` followed by `resize2fs /dev/demovg/demolv`, and confirm with
`df -h` that the mounted filesystem actually grew. Clean up afterward with `umount`, `lvremove`, `vgremove`,
`pvremove`, and `losetup -d` on both loop devices, in that order, and explain why that order matters.
