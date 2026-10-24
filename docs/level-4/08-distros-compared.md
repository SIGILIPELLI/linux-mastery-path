---
description: "Debian/Ubuntu, RHEL/Fedora, Arch and Alpine compared on init system, package manager, release model and libc — documented, not run."
---

# 08 · Linux Distros Compared: Debian, RHEL, Arch & Alpine

!!! note "Documentation-based lesson"
    Unlike almost every other lesson in this course, this one **cannot** be verified by running commands — it's
    a comparison *across* distributions, and this course's lab environment is one specific distro (Ubuntu). The
    facts below are drawn from each project's own current documentation as of October 2026 and are the kind of
    thing that occasionally shifts (a release cadence changes, a default swaps) — treat specific version numbers
    and dates as a snapshot, and the structural differences (init system, package format, philosophy) as durable.

Every lesson in this course ran on Ubuntu, a Debian derivative. The concepts — the filesystem model, permissions,
systemd, namespaces, netfilter — are genuinely the same across every mainstream distro, because they're kernel
and (mostly) systemd features, not distro-specific inventions. What *does* differ, and differs enough to matter
the first time you work on an unfamiliar distro, is covered here.

## Four distros, four different answers to the same questions

**Debian / Ubuntu** — `dpkg`/APT package management (Level 1, Lesson 9), `systemd` init, a conservative,
stability-first release philosophy on Debian itself (new "stable" releases roughly every two years, each
supported for years afterward) with Ubuntu layering a faster, more opinionated release cadence (a new release
every six months, with designated LTS releases — like the 26.04 LTS this course's lab VM runs — supported far
longer) on top of the same Debian package base.

**RHEL / Fedora** — `rpm`/DNF package management (the direct structural analogue to dpkg/APT from Level 1,
Lesson 9), `systemd` init (same as Debian/Ubuntu — this is not a point of difference), SELinux as the default LSM
(instead of AppArmor — Level 3, Lesson 6) and a split release model: Fedora is the fast-moving upstream (roughly
twice yearly releases, shorter support windows, newer package versions sooner), and RHEL (and its rebuilds —
Rocky Linux, AlmaLinux) is the long-support-window downstream, intentionally built from a point-in-time Fedora
base and then held stable for years, the enterprise-oriented mirror of Ubuntu's LTS philosophy.

**Arch Linux** — `pacman` package management, a genuinely different philosophy from both of the above:
**rolling release**, meaning there is no "Arch 13" or "Arch 26.04" — the system is continuously updated to the
latest packages, with no fixed release boundary at all. This trades predictability (a package version changing
underneath you between any two `pacman -Syu` runs) for always having current software, and Arch's own wiki and
documentation culture is widely regarded as exceptionally thorough — a reason people reach for it even without
running Arch itself.

**Alpine Linux** — the structural outlier of the four: `apk` package management, **OpenRC** instead of `systemd`
as its init system (a real, simpler init framework rather than systemd's broader scope), and most
significantly, **musl** instead of **glibc** as its C library, plus BusyBox instead of GNU coreutils for most
basic utilities (both mentioned in Level 1, Lesson 1 as the reason some scripts behave differently on Alpine).
Alpine's small footprint (a base image measured in single-digit megabytes) is exactly why it's the default base
for a huge share of container images — but that same musl/BusyBox substitution is also the most common reason a
script, binary, or `glibc`-specific behavior that "works everywhere" quietly breaks specifically on Alpine.

## How It Actually Works

The deepest, most consequential split here isn't package manager syntax — it's **glibc vs musl**. glibc is
larger, implements some long-standing GNU-specific extensions and behaviors, and is what the overwhelming
majority of prebuilt Linux binaries are compiled and tested against. musl is smaller, more strictly standards-
conforming in some areas, and deliberately omits some glibc extensions — which means a binary compiled against
glibc will often simply **not run** on an Alpine (musl) system at all without recompilation, a real and common
surprise for anyone moving a prebuilt binary or a Docker image's base layer from a glibc distro to Alpine. This
single difference accounts for more real-world "works on my machine" pain than every other distro difference on
this page combined.

The **rolling vs point-release** distinction (Arch vs. everything else here) is a genuine, deliberate tradeoff in
system design philosophy, not a maturity gap: a point-release distro batches and tests a coherent snapshot of
package versions together before calling it a numbered release, giving you predictability and a known-tested
combination; a rolling release gives you the newest packages continuously, at the cost of needing to handle
occasional breaking changes between any two updates rather than only at major-version boundaries.

## Common mistakes

- **Assuming a shell script tested only on Ubuntu/Debian will behave identically on Alpine.** Between
  `bash`-specific syntax (Alpine's default `/bin/sh` is often a much more limited shell, not bash, unless bash is
  explicitly installed) and the glibc/musl gap, this is one of the single most common container-build surprises.
- **Treating "Fedora" and "RHEL" as interchangeable because they share a package format.** Fedora runs noticeably
  newer package versions with a shorter support window — testing exclusively on Fedora and deploying to RHEL (or
  vice versa) can hit real version-skew issues the shared `rpm` format doesn't protect against.
- **Picking Arch for a production server because "it has the newest packages."** The same property that makes
  Arch appealing for a personal, actively-maintained desktop (always current) is a real operational cost for a
  server you don't want to babysit through rolling updates — point-release distros with long support windows
  exist specifically for that use case.

## Exercise

Pick any one tool you use daily (a shell, an editor, a language runtime) and look up how it's packaged and what
version is currently available on Debian stable, Ubuntu's current LTS, Fedora's current release, and Alpine's
current stable branch. Note which ones ship the newest version, which ship the oldest, and connect the pattern
you find back to each distro's release philosophy from this lesson.
