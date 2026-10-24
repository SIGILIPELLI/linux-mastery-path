---
description: "Mount fields in /etc/fstab, what a bind mount really does, and a real loopback NFS export and mount end to end."
---

# 05 · Mounting, fstab & Network Filesystems

"Mounting" a filesystem is the operation that connects a block device's (or network share's, or bind-mounted
directory's) contents into the single tree rooted at `/` (Level 1, Lesson 3) at some chosen point. `/etc/fstab`
is just a declarative list of mounts to perform automatically at boot, and once you've seen its fields and one
non-obvious mount type (a bind mount) done by hand, the file stops being a wall of cryptic options.

## Reading /etc/fstab

```text
$ cat /etc/fstab
LABEL=cloudimg-rootfs	/	 ext4	discard,commit=30,errors=remount-ro	0 1
LABEL=BOOT	/boot	ext4	defaults	0 2
LABEL=UEFI	/boot/efi	vfat	umask=0077	0 1
```

(Real `/etc/fstab` from this course's lab VM.) Each line has six fields: the device (here identified by
filesystem **label**, which survives a device renumbering `/dev/vda1` → `/dev/vda2` in a way a hardcoded path
wouldn't), the mount point, the filesystem type, a comma-separated options list, a legacy `dump` flag (almost
always `0` now — most systems don't use the old `dump` backup utility), and an `fsck` pass number (`0` = never
check; `1` for the root filesystem, checked first; `2` for everything else, checked after root). `findmnt` shows
the *live*, currently-active view of the same information, which can differ from `fstab` if something was mounted
by hand after boot rather than declared there:

```text
$ findmnt /
TARGET SOURCE    FSTYPE OPTIONS
/      /dev/vda1 ext4   rw,relatime,discard,errors=remount-ro,commit=30
```

## Worked example: a real bind mount

```text
$ sudo mkdir -p /srv/source /srv/target
$ sudo bash -c "echo original-content > /srv/source/file.txt"
$ sudo mount --bind /srv/source /srv/target
$ cat /srv/target/file.txt
original-content
$ mount | grep "srv/target"
/dev/vda1 on /srv/target type ext4 (rw,relatime,discard,errors=remount-ro,commit=30)
```

(Real output.) A **bind mount** doesn't involve a different filesystem or device at all — it makes the *same*
directory's contents visible at a second path simultaneously. Notice `mount`'s own output: it still reports the
source as `/dev/vda1`, the same device root lives on, because a bind mount isn't a new filesystem instance, it's
an additional mount-table entry pointing the kernel's path resolution at an *existing* directory's inode from a
second location. Writes through either path affect the same underlying files — this is exactly the mechanism
container runtimes use to expose a host directory inside a container's filesystem namespace, and it's what Level
2's package-management and Level 1's filesystem lessons both assumed was happening "underneath" without naming it.

## Worked example: a real NFS export and mount, loopback

```text
$ sudo mkdir -p /srv/nfsshare
$ echo shared-via-nfs | sudo tee /srv/nfsshare/greeting.txt
$ echo "/srv/nfsshare 127.0.0.1(rw,sync,no_subtree_check,no_root_squash)" | sudo tee /etc/exports
$ sudo exportfs -ra
$ sudo systemctl restart nfs-kernel-server

$ sudo mount -t nfs 127.0.0.1:/srv/nfsshare /mnt/nfsclient
$ cat /mnt/nfsclient/greeting.txt
shared-via-nfs
$ mount | grep nfsclient
127.0.0.1:/srv/nfsshare on /mnt/nfsclient type nfs4 (rw,relatime,vers=4.2,rsize=524288,wsize=524288,
  proto=tcp,sec=sys,clientaddr=127.0.0.1,...)
```

(Real output — an actual NFS server and client, running against each other over loopback on this course's lab
VM.) `/etc/exports` is the NFS server's own version of a declarative mount list — one line per shared directory,
naming which clients may mount it (`127.0.0.1` here, but normally a subnet or hostname) and with what options:
`rw` (read-write), `sync` (acknowledge writes only once actually committed, the safe default), `no_subtree_check`
(skip an expensive consistency check most modern setups don't need), `no_root_squash` (don't remap the client's
root user to an unprivileged one — fine for this loopback demo, a real security consideration on a real network).
`mount`'s output on the client side shows it negotiated **NFSv4.2** automatically and reports real protocol-level
details — read/write buffer sizes, the TCP transport, the security mode — that only exist because this is a real
network filesystem conversation, not a local block device.

## How It Actually Works

All three mount types in this lesson — a normal disk mount, a bind mount, and NFS — go through the same kernel
entry point, the **VFS (Virtual Filesystem Switch)**: a common interface every filesystem driver implements
(`open`, `read`, `write`, `readdir`...), which is exactly why `cat` and `ls` work identically whether the path
underneath happens to be ext4, a bind-mounted directory, or a remote NFS export. The VFS keeps a tree of **mount
structures**, and mounting is fundamentally the operation of grafting one filesystem's root (or, for a bind mount,
an arbitrary existing directory) onto a path in that tree. A bind mount is the simplest possible case — the
"filesystem" being grafted in is just another part of the *same* already-mounted filesystem, reached by inode
rather than by a new block device. NFS is the most elaborate case: the NFS client driver, instead of talking to a
local block device, serializes each VFS operation into an RPC call sent over the network to the NFS server, which
performs the real `read()`/`write()` against its own local filesystem and returns the result — the client-side
application code calling `read()` has no idea its request just went over a network at all.

## Common mistakes

- **Forgetting that a bind mount of a directory doesn't automatically propagate newly-created mounts inside it**
  (in the default private-mount mode) — nested mounts created after the bind mount was established may not be
  visible on the other side unless shared/mount-propagation options are explicitly set.
- **Editing `/etc/fstab` with a typo and rebooting without testing first.** A broken `fstab` entry for a non-root
  filesystem can leave the system booting into an emergency shell rather than finishing boot — `mount -a` (which
  reads and attempts every `fstab` entry without rebooting) is the safe way to test a new line before trusting it
  to a reboot.
- **Using `no_root_squash` on a real, multi-host NFS export without understanding the exposure.** It means any
  client machine's root user can act as root on the server's exported files — reasonable on an isolated loopback
  demo like this lesson's, a real risk on an actual multi-tenant network.

## Exercise

Create your own bind mount of any directory onto an empty one, write a file through the *new* mount point, and
confirm (via the original path) that it's the same underlying storage, not a copy. Then, if you have a second
machine or VM available, repeat this lesson's NFS export against it instead of loopback, and compare `mount`'s
reported protocol version and options to what you saw here.
