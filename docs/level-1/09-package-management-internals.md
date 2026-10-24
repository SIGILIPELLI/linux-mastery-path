---
description: "What dpkg/APT and rpm/DNF actually track on disk, how dependency resolution works, and what a package install really does."
---

# 09 · Package Management Internals: dpkg/APT vs RPM/DNF

"Install this package" sounds like one action, but on Linux it's really at least three: unpack files to disk,
record exactly which files belong to which package (so a later uninstall knows what to remove and nothing more),
and verify the package's declared dependencies are satisfiable. Two package-management lineages dominate Linux:
the Debian/Ubuntu family (`dpkg` + APT) and the Red Hat/Fedora family (`rpm` + DNF). They differ in file formats and
tooling but solve the identical underlying problem the same structural way.

## The low-level tool vs the dependency-solving tool

**`dpkg`** is the low-level tool that actually installs `.deb` files and maintains the on-disk database of what's
installed — but it has no concept of fetching anything from the internet and will flatly refuse to install a
package whose dependencies aren't already present. **APT** (`apt`/`apt-get`) sits above `dpkg`: it manages
repository lists (`/etc/apt/sources.list` and `/etc/apt/sources.list.d/`), downloads `.deb` files, and crucially
**resolves dependency graphs** — figuring out the full set of packages (and compatible versions) needed to satisfy
what you asked for, then handing the actual installation work down to `dpkg`. The Red Hat lineage has the exact
same split: `rpm` is the low-level installer/database tool (directly analogous to `dpkg`), and `DNF` (the successor
to `yum`) is the repository-aware dependency resolver sitting above it (directly analogous to APT).

## Worked example: what a package really leaves on disk

```text
$ dpkg -L curl | head -n10
/.
/usr
/usr/bin
/usr/bin/curl
/usr/bin/wcurl
/usr/share
/usr/share/doc
/usr/share/doc/curl
/usr/share/doc/curl/NEWS.Debian.gz
/usr/share/doc/curl/README.Debian

$ dpkg -S /usr/bin/curl
curl: /usr/bin/curl

$ dpkg -s curl | head -n8
Package: curl
Status: install ok installed
Priority: optional
Section: web
Installed-Size: 508
Maintainer: Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>
Architecture: arm64
Multi-Arch: foreign

$ apt-cache depends curl | head -n4
curl
  Depends: libcurl4t64
  Depends: libc6
  Depends: zlib1g
```

(Real output from this course's Ubuntu 26.04 lab VM.) `dpkg -L curl` is the package's exact file manifest — every
path `dpkg` will remove if you later run `apt remove curl`, and nothing more; this manifest, not a guess based on
install location, is how uninstalling a package doesn't accidentally sweep up files some *other* package also
happens to keep nearby. `dpkg -S` runs that lookup in reverse: given a path, which installed package owns it —
indispensable when you find a file and need to know what put it there. `dpkg -s` is the package's **status
record**: its declared metadata and, critically, the literal string `install ok installed`, which is `dpkg`'s own
state machine value, not just "yes/no installed" (a half-finished install, interrupted mid-way, shows a different
status like `install reinstreq`, which is exactly what `dpkg --configure -a` is built to detect and fix).
`apt-cache depends` shows the dependency **graph edges** APT has to satisfy — `libcurl4t64`, `libc6`, `zlib1g` —
each of which has its own dependencies in turn, and APT's actual job is finding one consistent, available version
of every package in that whole transitive closure.

## How It Actually Works

Both `dpkg` and `rpm` maintain their installed-package records as **flat local databases** — `dpkg`'s live under
`/var/lib/dpkg/` (the `status` file and `info/` directory of per-package file lists and maintainer scripts);
`rpm`'s live in `/var/lib/rpm/` (historically Berkeley DB, now commonly SQLite on modern Fedora/RHEL). An
"install" isn't really one atomic operation from the kernel's point of view: it's unpacking an archive to disk
*and* appending/updating rows in this local database, plus running any package-supplied maintainer scripts
(`postinst`, `preinst` for `.deb`; `%post`, `%pre` scriptlets for `.rpm`) that do extra setup a plain file copy
can't — creating a system user, enabling a `systemd` service, migrating a config file format. This is exactly why
interrupting a package manager mid-operation (a killed `apt` process, a lost SSH session during `dnf update`) can
leave a system in a genuinely inconsistent state: the database might record a package as installed while its
maintainer script never finished running, which is what commands like `dpkg --configure -a` (replay unfinished
maintainer scripts) and `rpm --rebuilddb` exist to repair.

**Dependency resolution** is, in the general case, an NP-hard constraint-satisfaction problem: given a universe of
packages each with version-ranged dependencies and conflicts, find a consistent set that satisfies everything
requested. Both APT (via its internal solver, or the newer `libsolv`-based backends some distros use) and DNF (via
`libsolv` directly, shared with other distros including openSUSE's Zypper) solve this with SAT-style solvers rather
than naive recursive descent, because naive dependency-chasing can get stuck in situations a real solver resolves
cleanly: package A needs B >= 2.0, package C needs B < 2.0, and the solver has to recognize that A and C simply
can't both be installed rather than install a broken partial result. The *packaging format* difference (`.deb`
being `ar` archives of compressed tarballs plus metadata; `.rpm` being `cpio` archives with an RPM-specific header)
is almost incidental compared to this shared solver architecture underneath both ecosystems.

## Common mistakes

- **Deleting files a package installed, by hand, instead of removing the package.** This desyncs the package
  database from reality — `dpkg`/`rpm` still believe the file exists and "belongs" to that package, which can
  cause confusing failures on the next upgrade or a false sense that removing the package later cleaned everything
  up (it won't try to delete a file it can already see is gone, but anything *you* added in that location stays).
- **Assuming a package being "installed" means its setup fully completed.** As covered above, maintainer
  scripts can fail or be interrupted independently of the file unpacking step — always check actual service state
  (Level 2) after installing something that's supposed to start a daemon, rather than trusting install exit code
  alone.
- **Mixing APT/dpkg repositories of different Ubuntu/Debian releases on one system** ("Frankendebian") expecting it
  to "just work" because the package format is the same — the solver will often find *a* technically consistent
  combination, but one that mixes library ABI versions never tested together, which is a common cause of mysterious
  crashes that package-format compatibility alone doesn't protect against.

## Exercise

Pick a small package you have installed (or install one you don't need long-term, like `curl` or `jq`), and run
`dpkg -L <package>` (or `rpm -ql <package>` on an RPM-based system) to see its full file manifest. Then run
`apt-cache depends <package>` (or `dnf repoquery --requires <package>`) and, for just the first two dependencies
listed, look up *their* dependencies in turn — by hand, you'll feel exactly why this needs an automated solver
once a real application with dozens of transitive dependencies is involved.
