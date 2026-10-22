---
description: "LVM volumes and snapshots, RAID levels with capacity math, and a real XOR parity rebuild that also shows the write hole."
---

# 05 · LVM, RAID & Storage Layers

Between a raw disk and a filesystem, Linux can insert layers that add flexibility or redundancy: **LVM** (resize and snapshot volumes), **software RAID** (`md`, survive disk failure), and **encryption** (LUKS/dm-crypt).
They stack, each presenting a block device to the next. This lesson explains what each layer buys you and what it costs, and demonstrates RAID's central trick (parity) with real arithmetic.

!!! note "What was run"
    `pvcreate`, `lvextend`, `mdadm`, `cryptsetup` and friends are Linux tools and **were not run** here; they are described from their man pages and standard practice. The **Python RAID model below was run**: capacity formulas, an
    XOR-parity rebuild and a write-hole demonstration are real computations, but they model the *idea*, not the Linux `md` implementation. See Level 1 · Lesson 01.

## LVM: flexible volumes

```text
physical disks/partitions → PV (physical volumes) → VG (volume group: a pool) → LV (logical volumes) → filesystem
   /dev/sdb1, /dev/sdc1         pvcreate                 vgcreate data_vg          lvcreate -L 50G -n www data_vg
```

- A **VG** pools the space of one or more PVs, divided into fixed-size **extents** (4 MiB by default).
- An **LV** is a set of extents, possibly spread across PVs, that appears as `/dev/data_vg/www` (and `/dev/mapper/data_vg-www`) and gets a filesystem like any partition.
- Why bother? You can **grow** an LV (and its filesystem) online, move extents between disks (`pvmove`) to retire a disk, and take **snapshots**.

```bash
sudo pvcreate /dev/vdb /dev/vdc                     # not run
sudo vgcreate data_vg /dev/vdb /dev/vdc
sudo lvcreate -L 50G -n www data_vg
sudo mkfs.ext4 /dev/data_vg/www && sudo mount /dev/data_vg/www /var/www
sudo lvextend -r -L +20G /dev/data_vg/www           # -r also resizes the filesystem (ext4/xfs growth)
sudo lvcreate -s -L 5G -n www_snap /dev/data_vg/www # copy-on-write snapshot with 5G of change space
```

**Snapshots** are copy-on-write: the snapshot initially holds nothing, and each block that changes in the origin is first copied into the snapshot's reserved space. Therefore a snapshot's size is "how much will change", and a classic LVM snapshot
**becomes invalid when its change space fills up**. Use snapshots for a consistent backup window (Level 4 · 02), then remove them: they slow writes while they exist. Thin provisioning lets LVs claim more space than physically exists; powerful and dangerous without monitoring (a full thin pool
corrupts volumes).

## Software RAID

| Level | Layout | Usable capacity (n disks of size s) | Failures tolerated |
|---|---|---|---|
| **0** | Stripe | n·s | **0** (any disk loss loses everything) |
| **1** | Mirror | s | n−1 |
| **5** | Stripe + 1 distributed parity | (n−1)·s | 1 |
| **6** | Stripe + 2 distributed parities | (n−2)·s | 2 |
| **10** | Mirrored pairs, striped | (n/2)·s | 1 per pair (two in the *same* pair is fatal) |

Computed with the model below for 4,000 GB disks:

```text
level  disks  size  usable  failures tolerated
    0      4  4000   16000  0
    1      2  4000    4000  1
    5      4  4000   12000  1
    6      6  4000   16000  2
   10      4  4000    8000  1 per mirror pair (up to n/2, but 2 in the same pair is fatal)
```

**RAID is availability, not backup.** It keeps the machine up through a disk failure; it faithfully replicates your `rm -rf`, a corruption bug, ransomware and a fat-fingered `mkfs` to every disk. Back up separately (Level 4 · 02).

### How parity works (run)

RAID 5's parity block is the **XOR** of the data blocks in a stripe. Because XOR is its own inverse, any one missing block equals the XOR of all the others, including parity.

```python
"""RAID capacity/tolerance arithmetic and a parity (XOR) demonstration. Pure Python."""
import os, itertools
def usable(level, n, size_gb):
    if level == 0:  assert n >= 2; return n * size_gb, 0
    if level == 1:  assert n >= 2; return size_gb, n - 1
    if level == 5:  assert n >= 3; return (n - 1) * size_gb, 1
    if level == 6:  assert n >= 4; return (n - 2) * size_gb, 2
    if level == 10: assert n >= 4 and n % 2 == 0; return (n // 2) * size_gb, "1 per mirror pair (up to n/2, but 2 in the same pair is fatal)"
    raise ValueError(level)

def xor_blocks(*blocks):
    out = bytearray(len(blocks[0]))
    for b in blocks:
        for i, x in enumerate(b): out[i] ^= x
    return bytes(out)

def stripe_with_parity(data, blocksize, ndata):
    """Split data into stripes of ndata blocks; return list of (blocks, parity)."""
    pad = (-len(data)) % (blocksize * ndata); data += b"\0" * pad
    stripes = []
    for off in range(0, len(data), blocksize * ndata):
        blocks = [data[off + i * blocksize: off + (i + 1) * blocksize] for i in range(ndata)]
        stripes.append((blocks, xor_blocks(*blocks)))
    return stripes

def rebuild(stripe_blocks, parity, lost_index):
    survivors = [b for i, b in enumerate(stripe_blocks) if i != lost_index]
    return xor_blocks(parity, *survivors)

if __name__ == "__main__":
    print("level  disks  size  usable  failures tolerated")
    for lvl, n in [(0, 4), (1, 2), (5, 4), (6, 6), (10, 4)]:
        u, f = usable(lvl, n, 4000); print(f"{lvl:>5}  {n:>5}  4000  {u:>6}  {f}")
    msg = b"The quick brown fox jumps over the lazy dog."
    st = stripe_with_parity(msg, 8, 3)
    print("stripes:", len(st), "| first stripe blocks:", [b for b in st[0][0]], "| parity hex:", st[0][1].hex())
    blocks, parity = st[0]
    rec = rebuild(blocks, parity, 1)
    print("lost block 1 =", blocks[1], "| rebuilt from parity + survivors =", rec, "| equal:", rec == blocks[1])
    lost2 = xor_blocks(parity, blocks[2])
    print("two blocks lost (1 and 0), only one parity: cannot recover; XOR of parity^block2 gives", lost2.hex(), "= block0^block1:", lost2 == xor_blocks(blocks[0], blocks[1]))
    # write hole demo: update data block but crash before parity update
    new0 = b"XXXXXXXX"; stale_parity = parity
    rec_bad = rebuild([new0, blocks[1], blocks[2]], stale_parity, 1)
    print("write-hole: data updated, parity stale -> rebuilt block1 =", rec_bad, "(corrupt) vs true", blocks[1])
```

Output:

```text
stripes: 2 | first stripe blocks: [b'The quic', b'k brown ', b'fox jump'] | parity hex: 59277f7274776a33
lost block 1 = b'k brown ' | rebuilt from parity + survivors = b'k brown ' | equal: True
two blocks lost (1 and 0), only one parity: cannot recover; XOR of parity^block2 gives 3f4807521e020743 = block0^block1: True
write-hole: data updated, parity stale -> rebuilt block1 = b'g\x10_\nFZ_\x1b' (corrupt) vs true b'k brown '
```

Three lessons from that run. (1) Losing one block of the stripe is fully recoverable: `b'k brown '` came back exactly. (2) Losing two leaves one equation with two unknowns: parity ^ block2 gave `block0 ^ block1`, which can't separate them,
which is why RAID 5 tolerates one failure and **why a second failure during rebuild is catastrophic**. Large disks make rebuilds take many hours, during which the array has no redundancy, one reason RAID 6 or mirrors are preferred for big drives. (3) The **write hole**: if power fails
after a data block is updated but before the parity is, the stripe is *inconsistent*, and a later rebuild computes garbage for a block that was never touched (the corrupt output above). Linux `md` mitigates this with a write-intent bitmap, a journal
device, or "ppl" (partial parity log); hardware controllers use a battery-backed cache. Filesystems with end-to-end checksums (Btrfs, ZFS) detect it.

### mdadm basics (not run)

```bash
sudo mdadm --create /dev/md0 --level=1 --raid-devices=2 /dev/vdb /dev/vdc
cat /proc/mdstat                         # array state and rebuild progress (Level 3 · 03)
sudo mdadm --detail /dev/md0
sudo mdadm --manage /dev/md0 --fail /dev/vdb --remove /dev/vdb    # replace a dead disk, then --add the new one
sudo mdadm --detail --scan >> /etc/mdadm/mdadm.conf               # so it assembles at boot
```

Monitor it (`mdadm --monitor`, or alerts on `/proc/mdstat` showing `[U_]`), because a degraded array that nobody notices is one failure from data loss. Also watch SMART data (`smartctl -a`) for early warnings.

## Encryption and stacking

LUKS (`cryptsetup`) encrypts a block device with a key derived from a passphrase or key file; the encrypted device (`/dev/mapper/crypt`) then carries LVM or a filesystem. Typical stack on a server: `disk → partition → mdraid → LUKS → LVM → ext4`. Each layer adds a failure mode and
a recovery procedure (an unlockable LUKS volume at boot waits for a passphrase unless you configure network unlock or a key file), so only stack what you need and **document the order**.

## How It Actually Works

LVM and `md` are implemented by the kernel's **device mapper** and **md** drivers. They take a request for a block on the virtual device and translate it to blocks on the underlying devices: LVM adds an offset through its extent map; RAID 0 distributes by stripe
index; RAID 1 duplicates writes and picks a replica for reads; RAID 5 computes parity (read-modify-write: read the old data and old parity, XOR in the change, write both). The filesystem above never knows. That transparency is also why a filesystem
`fsck` can't fix problems rooted below it, and why performance depends on alignment between stripe size, filesystem block size and I/O size.

## Common mistakes

- **Treating RAID as a backup.**
- **RAID 5 on very large disks** with no plan for the rebuild window and second-failure risk.
- **Not monitoring degraded arrays.**
- **LVM snapshots left in place** until they fill and become invalid.
- **Thin pools overcommitted** with no free-space alarm.
- **Growing the LV but not the filesystem** (or the reverse).
- **No documented layer order** for encrypted, RAID, LVM stacks.
- **Mixed-size or mixed-speed disks** in RAID 0/5 limiting capacity to the smallest.

## Exercise

1. Extend the model with RAID 6 using two independent parities (hint: the second parity uses a different coefficient in GF(2^8)), or read about "P+Q" parity and explain in your own words why it survives two losses.
2. Using the model, compute the usable capacity and fault tolerance for 8 disks of 8 TB for RAID 5, 6 and 10, and decide which you'd use for a database; justify.
3. On a Linux VM with three small virtual disks, build an `md` RAID 5 array, fail one disk, observe `/proc/mdstat`, and rebuild.
4. Create an LV, fill 80% of a snapshot's change space and watch it with `lvs`; what happens at 100%?
