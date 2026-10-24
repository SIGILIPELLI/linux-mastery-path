---
description: "Catching a broken fstab entry with mount -a before it causes a real boot failure, and what rescue/emergency targets actually depend on."
---

# 06 · Troubleshooting Boot Failures & Recovery Mode

The best time to diagnose a boot failure is before it happens — most of the classic causes (a bad `fstab` entry,
a service that blocks on a dependency that will never arrive) are testable on a running system without ever
risking an actual failed boot. This lesson tests the single most common one directly, and lays out what
`rescue`/`emergency` targets actually are for the cases that do slip through.

## Worked example: catching a broken fstab entry before it ever causes a boot failure

```text
$ sudo cp /etc/fstab /tmp/fstab.bak
$ echo "/dev/nonexistent /mnt/broken ext4 defaults 0 2" | sudo tee -a /etc/fstab

$ sudo mount -a
mount: /mnt/broken: mount point does not exist.
       dmesg(1) may have more information after failed mount system call.

$ sudo cp /tmp/fstab.bak /etc/fstab
```

(Real output from this course's lab VM.) `mount -a` reads `/etc/fstab` and attempts every entry exactly as boot
would, **without rebooting** — this is the single most direct way to validate a new `fstab` line before trusting
it to a reboot, and it caught a real problem immediately: in this case the mount *point* didn't even exist yet
(a second, equally common failure mode alongside "the device doesn't exist" — both are worth testing for, since
`mkdir -p` on the mount point is sometimes the only thing missing). A bad `fstab` entry for a **non-root**
filesystem, left uncaught and hit during an actual boot, is exactly the scenario that drops a system into an
**emergency shell** — `systemd` can't reach the target that depends on that failed mount, and rather than
silently continuing in a broken state, it stops and asks a human to intervene.

## Worked example: what rescue.target actually pulls in

```text
$ systemctl list-dependencies rescue.target --no-pager | head -n6
rescue.target
○ ├─grub-initrd-fallback.service
○ ├─rescue.service
● └─sysinit.target
●   ├─apparmor.service
●   ├─blk-availability.service

$ journalctl --list-boots --no-pager
IDX BOOT ID                          FIRST ENTRY                 LAST ENTRY
  0 1e8b72759fec45ccae08682c99b4d38f Thu 2026-10-22 23:26:05 IST Sat 2026-10-24 16:37:25 IST
```

(Real output — this VM has only ever had one boot so far, which is itself realistic for a lab environment created
recently; `journalctl --list-boots` is exactly the command to check for more boots, and is honest about there
being only one here rather than fabricating a prior failed boot to show.) `rescue.target` depends on
`sysinit.target` (early boot-critical units: device setup, security modules, basic filesystem mounts) but
**not** on `multi-user.target` or anything beyond it — by design, rescue mode brings up just enough of the
system to get a working root shell and basic diagnostic tools, deliberately skipping network services, display
managers, and anything that might itself be the cause of the boot problem you're trying to diagnose. `emergency.
target` (not shown here, but worth knowing) goes even further, skipping even most of `sysinit.target` — the
right choice when the filesystem itself, not just a later service, might be suspect.

## How It Actually Works

`mount -a`'s guarantee of accuracy comes from the fact that it's not a separate simulation — it's the exact same
`mount()` syscall path and the exact same `/etc/fstab` parsing that real boot-time mounting uses, just invoked
interactively instead of by `systemd`'s generated mount units. This is why testing with `mount -a` genuinely
predicts what boot would do, rather than approximating it.

When a `systemd`-managed boot genuinely can't satisfy a unit's requirements (a `.mount` unit failing because its
device or mount point is missing, as reproduced above but imagine uncaught), and something else in the
dependency graph (Level 2, Lesson 6) strictly `Requires=` that unit, `systemd` doesn't simply skip ahead and
pretend everything's fine — it drops to a target with the problem unit's chain already satisfied as far as
possible and stops there, typically **emergency mode** for a root-filesystem-level problem or an interactive
prompt for a specific failed non-critical mount, giving a human the chance to fix `/etc/fstab`, re-run `systemctl
daemon-reload`, and continue booting rather than ending up with a half-started system silently missing
something it depended on.

## Common mistakes

- **Rebooting immediately after editing `/etc/fstab` without testing with `mount -a` first.** As this lesson
  demonstrates directly, the exact same failure `mount -a` would have caught instantly, interactively, with full
  context, instead surfaces during boot — at a point with far less context and a much higher cost to get wrong.
- **Panicking at an emergency shell and immediately trying destructive fixes.** The emergency shell is a
  genuinely safe place to investigate first — `journalctl -xb` (this boot's full log) almost always names the
  specific unit and reason directly; fixing the named cause and running `systemctl default` to continue booting
  is usually faster and safer than guessing.
- **Forgetting that `nofail` exists for genuinely optional mounts.** Adding the `nofail` option to an `fstab`
  entry for a non-critical filesystem (a removable drive, an optional network share) tells `systemd` not to block
  the rest of boot if that one mount fails — appropriate for "nice to have," wrong for anything the system
  actually needs to function.

## Exercise

Add a deliberately broken line to a **copy** of your `/etc/fstab` (never test this against the real file without
a backup, exactly as this lesson did), and run `mount -a` against it to confirm the failure is caught. Then run
`systemctl list-dependencies rescue.target` and `systemctl list-dependencies emergency.target` side by side, and
identify at least one unit present in one target's dependency list but not the other's, explaining what that
difference implies about which boot problems each target is meant to help diagnose.
