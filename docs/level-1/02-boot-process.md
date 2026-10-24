---
description: "The Linux boot process end to end: firmware, bootloader, kernel decompression, initramfs, switching root, and the first userspace process."
---

# 02 · The Boot Process: Firmware, Bootloader & initramfs

Every troubleshooting guide for "my server won't start" assumes you know roughly where in the boot sequence things
went wrong. This lesson walks that sequence in order, because each stage fails in a different, recognizable way —
a firmware problem looks nothing like a bootloader problem, which looks nothing like a kernel panic, which looks
nothing like a failed service after boot.

## The stages, in order

1. **Firmware** (BIOS on older/legacy machines, UEFI on essentially everything made since the early 2010s) runs the
   instant the machine powers on. It initializes just enough hardware to find a boot device, then hands control to a
   bootloader. UEFI firmware reads boot entries from an EFI System Partition (a small FAT32 partition you can see
   with `fdisk -l` or `lsblk -f`) rather than scanning a disk's first sector the way legacy BIOS did.
2. **The bootloader** (GRUB, on most Linux distros) loads next. Its job is simple on paper — load a kernel image and
   an initramfs into memory and jump to the kernel — but it's also where you pick a kernel version, pass boot
   parameters (the famous `GRUB_CMDLINE_LINUX` you edit when debugging), or boot into a rescue/recovery target.
3. **The kernel** decompresses itself (kernel images are compressed to save disk space) and starts executing. At
   this point there is no filesystem, no process table, no `/`. The kernel's very first job is to mount a temporary
   root filesystem that lives entirely in RAM.
4. **initramfs** is that temporary root filesystem — a small compressed cpio archive, unpacked into RAM, containing
   just enough tools (`udev`, disk/RAID/LUKS drivers, busybox-style utilities) to find and mount the *real* root
   filesystem, which might be on an encrypted LVM volume the kernel can't reach without extra driver support that
   isn't worth compiling into every kernel permanently.
5. **`switch_root`** replaces the temporary initramfs root with the real root filesystem and execs the init system
   (`systemd` on most modern distros) as PID 1 — the point where this lesson hands off to Level 2's `systemd` lessons.

## Worked example: reading your own boot timeline

```text
$ systemd-analyze
Startup finished in 317ms (kernel) + 1.336s (initrd) + 2min 45.052s (userspace) = 2min 46.706s
graphical.target reached after 2min 7.329s in userspace.

$ systemd-analyze blame | head -n5
2min 2.688s cloud-init-network.service
   2min 147ms systemd-networkd-wait-online.service
       37.719s cloud-final.service
        1.946s snapd.seeded.service
        1.589s sys-devices-virtual-misc-rfkill.device

$ ls -la /boot/initrd.img-7.0.0-34-generic
-rw-r--r-- 1 root root 91123407 Sep 27 21:59 /boot/initrd.img-7.0.0-34-generic

$ lsinitramfs /boot/initrd.img-7.0.0-34-generic 2>/dev/null | grep -E "^usr/sbin/(lvm|cryptsetup)$|cryptsetup\.so"
usr/sbin/cryptsetup
usr/sbin/lvm
usr/lib/aarch64-linux-gnu/libcryptsetup.so.12
```

(Real output from this course's Ubuntu 26.04 lab VM.) `systemd-analyze`'s three-way split — kernel, **initrd**, and
userspace — is exactly stages 3–4–5: kernel self-init, then the initramfs running as its own timed phase, then
everything `systemd` orchestrates after `switch_root`. `systemd-analyze blame` tells you which *unit* took longest
once `systemd` was in control, and this VM's own numbers make a real teaching point: `cloud-init-network.service`
and `systemd-networkd-wait-online.service` dominate the boot at over two minutes each, because this is a
**cloud image** — it's built to wait for network configuration from a cloud provider's metadata service before
continuing, a cost a normal desktop or bare-metal install wouldn't pay. That's a genuinely useful "blame" result:
it correctly points at cloud-init's network wait, not at anything actually broken. `lsinitramfs` lets you look
inside the initramfs cpio archive without unpacking it by hand, and seeing real `lvm` and `cryptsetup` binaries in
there explains *why* an initramfs exists at all: the real root filesystem might be on an LVM volume inside a
LUKS-encrypted partition, and none of that can be assembled until drivers and tools for it are available — which is
exactly what the temporary RAM-based root provides before the real one is reachable.

## How It Actually Works

The reason there are *two* root filesystems in sequence (initramfs, then the real root) instead of one is a genuine
chicken-and-egg problem. To mount your real root filesystem, the kernel might need: a driver for your disk
controller, LVM's user-space tools to assemble logical volumes, `cryptsetup` to unlock an encrypted volume, and
`udev` to create the right device nodes in the right order as hardware is detected asynchronously. All of that is
substantial, versioned, and distro-specific — you don't want to compile it permanently into every kernel image, and
you don't want to hunt for it on a filesystem you haven't mounted yet. The initramfs solves this by being a tiny,
self-contained environment built *specifically for this machine's hardware and storage layout* at the time the
kernel package was installed (which is why `update-initramfs` or `dracut` reruns automatically after certain
package updates) — it carries exactly the drivers and tools needed to get from "nothing mounted" to "real root
mounted," then gets discarded.

`switch_root` (as opposed to a simple `chroot`) is also doing real work: `chroot` only changes what path a process
treats as `/`, but the initramfs environment has kernel filesystems like `/proc`, `/sys`, and `/dev` mounted, plus
possibly running processes (udev daemons) that need to be moved to the new root or killed cleanly. `switch_root`
handles unmounting the old root's special filesystems, remounting them under the new root, and killing anything
still running from the old one — a `chroot` alone would leave you with a half-torn-down environment.

## Common mistakes

- **Editing `/boot/grub/grub.cfg` directly.** This file is auto-generated by `grub-mkconfig`/`update-grub` from
  `/etc/default/grub` and the scripts in `/etc/grub.d/`; a manual edit survives exactly until the next kernel update
  regenerates the file and silently discards your change.
- **Assuming a "boot hang" always means a bootloader or firmware problem.** A hang after GRUB's menu but before a
  login prompt is very often a *userspace* problem — a `systemd` unit that's blocking on a dependency, a broken
  `fstab` entry the real root mount depends on — not a kernel or bootloader fault at all; `systemd-analyze blame`
  and the rescue/recovery boot target (Level 4) are the right next step, not reinstalling GRUB.
- **Forgetting to regenerate the initramfs after changing storage configuration.** Adding a new encrypted volume,
  switching RAID levels, or moving root onto LVM, and then not running `update-initramfs -u` (Debian/Ubuntu) or
  `dracut -f` (Fedora/RHEL), leaves you with an initramfs that doesn't know how to find your new root — the system
  boots the old initramfs successfully, then fails to find the real root and drops to an emergency shell.

## Exercise

Run `systemd-analyze` and `systemd-analyze blame` on any Linux machine you have access to. Identify: (1) whether
kernel time or userspace time dominates your boot, and (2) the single slowest unit in the blame list — then look up
(`systemctl cat <that-unit>`) what that unit actually does, and form a hypothesis for why it's slow (network wait,
disk wait, or genuine startup work).
