---
description: "How package managers work: repositories, signatures, dependencies, apt vs dnf vs apk, holds and updates, plus a Homebrew run."
---

# 08 · Package Management: apt, dnf & Friends

Linux software is installed from **packages**: archives containing files plus metadata (name, version, dependencies, scripts). A **package manager** resolves dependencies,
verifies signatures, installs files, and records exactly what it put where, so software can be upgraded and removed cleanly. It is also your main security patching channel (Level 4 · 05).

!!! note "What was run"
    There is no Debian, Fedora or Alpine system on the Mac used to write this course, so **`apt`, `dnf` and `apk` commands were not run**; they are described from the
    distributions' documentation as known in October 2026 and should be checked against your release. The one thing I could run is **Homebrew** (macOS's package manager,
    version 7.0.9 here), which has the same concepts; its read-only output (`brew deps`, `brew info`) is shown labelled. See Lesson 01.

## Anatomy of the system

```text
repository (signed index + package files)
        │  apt update / dnf makecache   (download the index)
        ▼
local index (what versions exist) ──► resolver ──► download ──► verify signature/hash ──► install files ──► run scripts ──► update the local database
```

- A **repository** is a server (or mirror) holding packages and a signed index. You configure which ones to trust (`/etc/apt/sources.list.d/`, `/etc/yum.repos.d/`).
- **Signatures** (GPG keys, or signed repository metadata) prove packages came from the repository's owner. Adding a repo means trusting its key with root privileges, because
  packages can run arbitrary scripts at install time.
- A package declares **dependencies** (other packages and versions), and the resolver picks a consistent set or explains the conflict.

## Command cheat sheet by family

| Task | Debian/Ubuntu (apt) | Fedora/RHEL (dnf) | Alpine (apk) |
|---|---|---|---|
| Refresh the package index | `apt update` | (done automatically; `dnf makecache`) | `apk update` |
| Upgrade installed packages | `apt upgrade` (`full-upgrade` may remove packages) | `dnf upgrade` | `apk upgrade` |
| Install | `apt install nginx` | `dnf install nginx` | `apk add nginx` |
| Remove (keep config) | `apt remove nginx` | `dnf remove nginx` | `apk del nginx` |
| Remove with config | `apt purge nginx` | n/a | n/a |
| Search | `apt search word` | `dnf search word` | `apk search word` |
| Show details | `apt show nginx` | `dnf info nginx` | `apk info nginx` |
| Which package owns a file? | `dpkg -S /usr/sbin/nginx` | `rpm -qf /usr/sbin/nginx` | `apk info -W /usr/sbin/nginx` |
| List a package's files | `dpkg -L nginx` | `rpm -ql nginx` | `apk info -L nginx` |
| Clean unused deps | `apt autoremove` | `dnf autoremove` | (automatic with virtual packages) |

The commands above are standard usage from each tool's manual and not run here. Notes: `apt update` only refreshes the *list*; `apt upgrade` actually changes software. Running
install on a stale index is a common source of "Unable to locate package" and 404 errors. Prefer `apt` over the older `apt-get` for interactive use, but scripts use
`apt-get -y` (the `apt` command's output isn't a stable interface), and in Docker builds combine update and install in one layer and clean the lists.

Low-level tools (`dpkg -i`, `rpm -i`) install a single package file **without resolving dependencies**; use them only when you must, and let `apt install ./file.deb` or `dnf install ./file.rpm` handle
dependencies.

## Dependency trees, run with Homebrew

Homebrew isn't a Linux manager, but dependency trees look the same. Run on macOS:

```text
$ brew deps --tree jq
jq
└── oniguruma
$ brew info jq | head -3
==> jq: stable 1.8.2 (bottled), HEAD
Lightweight and flexible command-line JSON processor
```

`jq` needs one library, `oniguruma`. Install `jq` and the manager installs both; remove `jq` and the library becomes an orphan that `autoremove` (`brew autoremove`) can delete. The same
idea in apt: `apt-mark showmanual` lists packages you asked for, versus packages installed only as dependencies. On Linux, `apt-cache rdepends` / `dnf repoquery --whatrequires`
show who depends on a package before you remove it.

## Versions, pinning, holding

A repository carries the versions the distribution chose for your release; you typically get **security fixes backported** to those versions rather than new upstream versions.
When you need a newer version you have options, in rough order of preference: the distribution's own backports/AppStream modules, the vendor's official repository
(add its signing key and source file; trust implications!), a container image, a language-specific manager (pip, npm; Level 4), or building from source into `/usr/local` or `/opt`.

```bash
apt-mark hold nginx            # keep this version during upgrades (Debian family)
apt-cache policy nginx         # installed vs candidate vs repo priorities
dnf versionlock add nginx      # plugin; or exclude= in dnf.conf (RHEL family)
```

Holds prevent surprise upgrades but also **prevent security fixes**, so every hold needs an owner and a review date.

## Unattended and reproducible updates

- Automatic security updates: `unattended-upgrades` (Debian family) or `dnf-automatic` (RHEL family). Good for fleets of simple servers; review reboot behaviour (Level 4 · 05).
- For reproducibility, pin versions in image builds (`apt-get install nginx=1.24.0-*`), mirror repositories internally, and record the package set (`dpkg -l`, `rpm -qa`) as a build artifact.

## How It Actually Works

Each installed package is recorded in a local database (`/var/lib/dpkg/status` for dpkg, an RPM database under `/var/lib/rpm` or `/usr/lib/sysimage/rpm`). That database is what lets `dpkg -S`
answer "which package owns this file?", what lets removal delete exactly the files that were installed, and what makes `/var` backup-worthy (Lesson 02). The resolver treats installation as constraint
solving: each package version has dependencies (`Depends`), conflicts and optional recommendations; it searches for a set that satisfies everything, preferring already-installed versions. Install scripts
(`preinst`, `postinst`) run as root to create users, enable services and update caches, which is why a repository key is a root-level trust decision and why packages can fail
halfway (`dpkg --configure -a` finishes interrupted installs). Config files marked as such are preserved, and on upgrade the tool asks or leaves a `.dpkg-new`/`.rpmnew` file when you've edited them.

## Common mistakes

- **Not running `apt update`** before install, or running `upgrade` expecting new software versions.
- **Adding random third-party repos or `curl | sudo bash`** installers without checking keys or content.
- **`pip install` with `sudo`** into system Python, which fights the package manager; use virtual environments.
- **Holding a package forever.**
- **Mixing repositories from different releases** ("frankendebian"), which breaks dependencies.
- **Deleting package-owned files by hand**, so the database no longer matches reality.
- **Installing build tools and caches in production images** and never cleaning them.

## Exercise

1. On a Debian/Ubuntu or Fedora machine, install `tree`, find which package owns `/usr/bin/tree`, list its files, then remove it and confirm the files are gone.
2. Find a package that is installed as a dependency only (apt: not in `apt-mark showmanual`) and explain why `autoremove` would delete it.
3. Check the update state of your system and list pending security updates (`apt list --upgradable` or `dnf updateinfo list security`).
4. On any machine, use your package manager's dependency tree command to find the three packages with the most dependents. What does that tell you about update risk?
