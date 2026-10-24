---
description: "Character vs block devices, major/minor numbers, and how udev names a newly-detected device and builds stable symlinks for it."
---

# 09 · Device Files, udev & /dev

`/dev/vda`, `/dev/null`, `/dev/sda1` — these look like ordinary files, sit in an ordinary-looking directory, and
yet none of them have any real content on disk the way `/etc/fstab` does. They're **device files**: a userspace
handle onto a kernel driver, identified by a pair of numbers you can see with a plain `ls -l`.

## Character vs block, and the two numbers that identify a driver

`ls -l` on a device file shows a leading `c` or `b` instead of the usual `-`/`d`/`l`: **`c`** for a **character
device** (data transferred as an unstructured stream — a terminal, `/dev/null`, `/dev/zero`), **`b`** for a
**block device** (data accessed in fixed-size blocks, addressable by position — a disk or disk partition). Where
a regular file's `ls -l` shows a size, a device file shows two numbers instead: **major**, identifying *which
driver* handles this device, and **minor**, identifying *which specific instance* that driver should talk to.

## Worked example: real device files and real udev-assigned names

```text
$ ls -l /dev/null /dev/zero /dev/vda /dev/vda1
crw-rw-rw- 1 root root   1, 3 Oct 22 23:26 /dev/null
crw-rw-rw- 1 root root   1, 5 Oct 22 23:26 /dev/zero
brw-rw---- 1 root disk 253, 0 Oct 22 23:28 /dev/vda
brw-rw---- 1 root disk 253, 1 Oct 22 23:28 /dev/vda1

$ udevadm info --query=all --name=/dev/vda
P: /devices/pci0000:00/0000:00:06.0/virtio2/block/vda
M: vda
N: vda
S: disk/by-diskseq/9
S: disk/by-path/pci-0000:00:06.0
S: disk/by-path/virtio-pci-0000:00:06.0
E: DEVNAME=/dev/vda
E: DEVTYPE=disk
E: DISKSEQ=9
E: MAJOR=253
E: MINOR=0
E: SUBSYSTEM=block
```

(Real output from this course's lab VM.) `/dev/null` and `/dev/zero` are both **character** devices (`c`) sharing
**major 1** — the kernel's generic memory-backed "pseudo-device" driver — distinguished from each other only by
**minor** (3 vs 5); the driver code uses the minor number to decide "this open is `/dev/null`, discard everything"
versus "this open is `/dev/zero`, return infinite zero bytes" without needing separate drivers at all. `/dev/vda`
is a **block** device (`b`), major `253`, the `virtio_blk` driver (this is a virtual machine, so its disk is a
paravirtualized virtio device, not a real SATA/NVMe controller — a real machine would show a different major tied
to its actual disk driver). `udevadm info` reveals that `/dev/vda` isn't the *only* name pointing at this device:
`S:` lines list **symlinks** udev created — `disk/by-diskseq/9`, `disk/by-path/pci-0000:00:06.0` — stable
alternate names under `/dev/disk/` that keep working even if `/dev/vda` were renumbered to `/dev/vdb` on a
different boot (which genuinely happens when disk detection order changes).

## How It Actually Works

Device *files* don't contain driver code — they're just a (type, major, minor) tuple the kernel's VFS layer uses
to look up which driver's `file_operations` table to call when a program `open()`s them. The **driver**, whether
built into the kernel or loaded as a module (Level 4), is what actually does something when `read()`/`write()`/
`ioctl()` happens on an open device file. This is why creating a device file by hand with `mknod` (rarely needed
today, but instructive) can point at a major/minor pair with *no* corresponding driver loaded — the file exists,
`ls -l` shows it, but opening it fails, because the number-to-driver mapping only means something once the kernel
side is actually present.

`/dev` itself is almost always `devtmpfs` — a kernel-populated, RAM-backed virtual filesystem (similar in spirit
to `/proc`/`/sys`, Level 1 Lesson 3) that the kernel fills in automatically as devices are detected, *before*
udev even starts. **udev**, a userspace daemon, listens for the kernel's device-detection events (via a netlink
socket) and does the work the kernel's own `devtmpfs` population doesn't: running the matching rules from
`/lib/udev/rules.d/` and `/etc/udev/rules.d/` to set correct permissions and ownership, trigger device-specific
setup (loading firmware, setting up a USB device's driver-specific quirks), and create the extra, human- and
automation-friendly symlinks shown above. This two-stage split — kernel creates the raw node immediately,
userspace enriches it slightly after — is exactly why a device can briefly exist as `/dev/sdb` with default,
possibly-wrong permissions for a moment right after a hotplug, before udev's rules finish applying.

## Common mistakes

- **Hardcoding `/dev/sda` (or similar plain device names) in scripts or `fstab` entries for anything other than
  the most disposable, single-disk scenario.** Device *enumeration* order (`sda` vs `sdb`) can change across
  reboots, especially with multiple disks or hot-swappable storage — the `by-uuid`, `by-label`, or `by-path`
  symlinks under `/dev/disk/` are the stable alternative udev exists partly to provide.
- **Assuming every device file under `/dev` currently works.** As explained above, the file can exist (created by
  `devtmpfs` or a stale `mknod`) with no corresponding driver loaded or hardware present — `ls -l` showing the
  entry isn't proof the device is usable.
- **Writing custom udev rules without testing them with `udevadm test` first.** A rule with a typo'd match
  condition can silently fail to apply (leaving default permissions) or, worse, match more devices than intended —
  `udevadm test /sys/class/.../<device>` runs the rule-matching logic without actually triggering real device
  changes, which is the safe way to iterate.

## Exercise

Run `ls -l /dev/null /dev/zero /dev/random /dev/urandom` and note which major/minor pairs are shared and which
differ. Then run `udevadm info --query=all --name=<your root disk device>` and list every stable symlink udev
created for it under `/dev/disk/` — explain, for at least one of them, a scenario where using that symlink instead
of the raw device name would have avoided a real problem.
