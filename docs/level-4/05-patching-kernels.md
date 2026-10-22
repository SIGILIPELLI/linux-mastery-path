---
description: "Patching in production: security updates, restarts after library updates, kernel reboots, live patching, and a tested Debian version comparator."
---

# 05 · Patching, Kernel Updates & Reboots

Most breaches exploit vulnerabilities for which a fix already existed. Patching is how you close that gap, but each patch can also break something, and some require restarting services or rebooting the machine. A good patching practice is boring and regular: know what's installed, apply security fixes promptly, test them first, roll out in stages, and be able to roll back.

!!! note "What was run"
    No package manager (`apt`, `dnf`) or kernel was available on the Mac used for this course, so **no patching command was run**. Distribution behaviours below are from general knowledge and documentation of those tools as I know them, and should be checked for your release. What I did run: a **Debian-style version comparison function with 15 pytest cases** on macOS. The test expectations come from my reading of the Debian Policy version-ordering
    rules; I could not cross-check them against `dpkg --compare-versions` here. See Level 1 · Lesson 01.

## What kinds of updates are there?

| Kind | Examples | Risk |
|---|---|---|
| **Security updates** | Fix for a CVE in OpenSSL, the kernel, sudo | Lowest per-package risk (distributions backport minimal fixes); highest cost of delay |
| **Bug-fix updates** | Stability fixes within a release | Low to medium |
| **Feature/version upgrades** | New major version of PostgreSQL, a new distribution release | High: behaviour changes, config migration |

Stable distributions patch by **backporting** the fix into the version they shipped rather than moving to a new upstream version. That is why version numbers look old (`openssl 3.0.x-0ubuntu1.5`) yet the vulnerability is fixed; read the package changelog (`apt changelog openssl`, `rpm -q --changelog openssl`) or the distribution's security tracker for CVE numbers, not the upstream version.

## Comparing versions correctly

Package versions are not decimal numbers. Debian versions have the form `[epoch:]upstream[-revision]` and a defined ordering: compare runs of digits numerically, letters and punctuation by a special order, `~` sorts **before** everything (so `1.0~rc1 < 1.0`), and a higher epoch always wins. RPM has similar but not identical rules. A tested implementation of the Debian algorithm:

```python
"""Compare Debian package versions: [epoch:]upstream[-revision], per the algorithm in the Debian Policy Manual (section on version ordering).
'~' sorts before everything, even the end of the string. Letters sort before non-letters."""
import re

def _split(v):
    epoch = 0
    if ":" in v: e, v = v.split(":", 1); epoch = int(e)
    if "-" in v: up, rev = v.rsplit("-", 1)
    else: up, rev = v, "0"
    return epoch, up, rev

def _order(c):
    if c == "~": return -1
    if c.isdigit() or c == "": return 0
    if c.isalpha(): return ord(c)
    return ord(c) + 256

def _cmp_part(a, b):
    while a or b:
        # compare the non-digit prefix character by character
        na, nb = re.match(r"\D*", a).group(), re.match(r"\D*", b).group()
        a, b = a[len(na):], b[len(nb):]
        for i in range(max(len(na), len(nb))):
            ca = _order(na[i]) if i < len(na) else 0
            cb = _order(nb[i]) if i < len(nb) else 0
            if ca != cb: return -1 if ca < cb else 1
        da, db = re.match(r"\d*", a).group(), re.match(r"\d*", b).group()
        a, b = a[len(da):], b[len(db):]
        ia, ib = int(da or 0), int(db or 0)
        if ia != ib: return -1 if ia < ib else 1
    return 0

def compare(v1, v2):
    e1, u1, r1 = _split(v1); e2, u2, r2 = _split(v2)
    if e1 != e2: return -1 if e1 < e2 else 1
    return _cmp_part(u1, u2) or _cmp_part(r1, r2)
```

```text
15 passed in 0.01s   (parametrised cases incl. 1.10 > 1.9, 1.0~rc1 < 1.0, 2:0.9 > 1:9.9, 1.0-1+deb12u1 > 1.0-1, 1.0-1ubuntu1 > 1.0-1)
sorted(["1.24.0-1", "1.24.0-1+deb12u1", "1.24.0-1+deb12u2", "1.24.0-2", "1.26.0~rc1-1", "1.26.0-1"]) keeps that order
```

Why bother? Lexical string comparison puts `1.10` before `1.9`, and "latest version" scripts built on `sort` without version awareness will pick the wrong package (GNU `sort -V` is closer but is not dpkg's algorithm). In production use `dpkg --compare-versions a lt b` or `apt-cache policy`, and use my function only to understand the rules. The vendor-style suffixes `+deb12u1` and `-1ubuntu1` encode *which patch level you have* within an upstream version: a security
fix is usually a higher revision of the same upstream version.

## The patching workflow

1. **Inventory**: know what's installed and where (`dpkg -l`, `rpm -qa`, config management facts, an SBOM), including containers and language dependencies, which the OS package manager does not update.
2. **Subscribe** to security notices (distribution mailing lists, `apt list --upgradable`, `dnf updateinfo list security`, vulnerability scanners).
3. **Prioritise** by exposure and severity: internet-facing services and remote-code-execution flaws first; set a policy with target times (critical in days, others in weeks).
4. **Test** in staging that mirrors production (same packages, same configuration), including a restart.
5. **Stage the rollout**: canary host, then a small batch, then the fleet, with health checks and the ability to stop (rolling-update practices from Lesson 03).
6. **Apply**: `apt-get update && apt-get -s upgrade` (simulate with `-s`), then upgrade; `dnf upgrade --security`.
7. **Restart what needs restarting** (below).
8. **Verify** (versions, health checks, logs) and record it.
9. **Have a rollback**: previous package versions in your mirror or cache (`apt install pkg=version`, `dnf history undo`), snapshots, or a redeploy of the last good image.

## Services keep running old code until restarted

Updating a library on disk does not change the copy already loaded in a running process. After a library security update (say `openssl`), every process still using the old library is vulnerable until restarted. Tools detect this:

```bash
needrestart                      # Debian/Ubuntu: lists services using outdated libraries and offers to restart them
dnf needs-restarting -s          # RHEL family: services needing restart;  -r tells whether a reboot is needed
sudo lsof +c 0 | grep -i 'DEL.*libssl'    # processes mapping a deleted (replaced) library file
```

(Not run.) The last command works because replaced libraries show as deleted mappings in memory (Level 1 · 03: the old inode lives on while mapped). Restart services in a controlled order, behind a load balancer; a full reboot is the surest way to get everything current.

## Kernel updates and reboots

The kernel is the one component that can't be replaced under a running system; a new kernel takes effect only after a **reboot**. A kernel security fix in an installed package that you haven't rebooted into does nothing. Check:

```bash
uname -r                                  # the running kernel
ls /boot/vmlinuz-* ; dpkg -l 'linux-image*' | grep ^ii    # installed kernels   (Debian family; rpm -q kernel on RHEL)
[ -f /var/run/reboot-required ] && cat /var/run/reboot-required*     # Debian/Ubuntu flag
```

If the installed kernel is newer than the running one, the machine is running a vulnerable kernel. (This is the "version string doesn't tell the whole story" caveat from Level 1 · 01: compare against the distribution's advisory.)

Strategies: **scheduled maintenance windows with rolling reboots** across redundant nodes (drain, patch, reboot, health-check, return, next); **live patching** (Canonical Livepatch, kpatch/kGraft in enterprise distributions) that applies some critical kernel fixes without a reboot, which is useful but doesn't cover every fix and doesn't replace periodic reboots; **immutable infrastructure** (replace instances with freshly built images, so patching is a rebuild). Keep at
least one older kernel installed as a boot fallback, and test that the machine comes back (a console or out-of-band access matters).

Pitfalls: a reboot that fails to bring up networking or a data mount (Level 2 · 04: a bad `fstab` line) turns a patch window into an outage; a DKMS-built driver module that fails to build for the new kernel; a kernel parameter or bootloader entry that was manually edited and gets overwritten; and `needrestart` auto-restarting something at the wrong time on a database host.

## Automatic updates

`unattended-upgrades` (Debian family) and `dnf-automatic` (RHEL family) can install security updates daily. Reasonable for small fleets of simple servers, with caveats: configure which origins are allowed (security only), email or log results, decide about auto-reboot (and in what window), exclude packages with risky restarts (databases) and still test. For managed fleets, prefer *orchestrated* patching (Lesson 03) with staging and health checks over each host updating itself at a random time.

## Beyond OS packages

Patching also covers language dependencies (pip, npm, Maven), container base images (rebuild when the base image gets a fix; Lesson 09), firmware and BIOS/microcode (`intel-microcode`, `fwupd`), network devices, and third-party repositories that bypass your distribution's security process. A vulnerability scanner or a software bill of materials ties these together.

## How It Actually Works

A package update replaces the files listed in the package's file manifest with the new ones: the package manager writes new files and renames them over old ones atomically, then runs maintenance scripts (restart hints, `ldconfig`, update the initramfs for kernel packages, update the bootloader entry). Running processes keep their open file descriptors and memory mappings of the *old* inodes, which remain on disk until closed, so they continue to execute the old code; this is
why restarts are needed. A new kernel is simply a new file in `/boot` plus a bootloader entry; only a reboot loads it. Live patching works by loading a kernel module that redirects calls to patched functions at runtime, so it can fix specific functions but not data-structure changes.

## Common mistakes

- **Comparing versions as strings or decimals.**
- **Believing the upstream version number** tells you if a CVE is fixed.
- **Not restarting services after library updates.**
- **Installing a new kernel and never rebooting.**
- **Patching everything at once** with no canary or rollback.
- **Ignoring non-OS dependencies** (containers, language packages).
- **Auto-reboot in the middle of the business day**, or never rebooting at all.
- **Pinning packages forever** (Level 1 · 08) and missing fixes.
- **Not testing that the machine boots** after a kernel update.

## Exercise

1. On a Debian/Ubuntu VM, run `apt list --upgradable`, simulate an upgrade with `apt-get -s upgrade`, apply security updates, and use `needrestart` to see what needs restarting. Record what you restarted and why.
2. Write a script that compares `uname -r` with the newest installed kernel package and exits non-zero if a reboot is pending, with a test that fakes both inputs (use the version function above for the comparison).
3. Design a rolling-patch procedure for a 6-node web tier behind a load balancer: drain, patch, reboot, verify, return, with abort conditions.
4. Take one container image you use and list which of its packages have security updates available since it was built.
