---
description: "The mainline/stable/longterm kernel split, read from kernel.org's real current release data, and how to tell which one you're running."
---

# 09 · Kernel Versions, LTS & Staying Current

"Which kernel version should I run" has a different right answer depending on whether you want the newest
features, the most tested stability, or multi-year support — because the kernel project itself maintains several
parallel release lines simultaneously, not one single version number moving forward.

## The three lines kernel.org actually maintains

**Mainline** is where new development lands first — the newest features, the newest hardware support, and the
least real-world testing time. **Stable** takes a mainline release once it's done and backports bugfixes-only
patches to it for a few months after the *next* mainline release ships, giving a short window of polish before
that line is retired. **Longterm (LTS)** takes certain mainline releases (not all of them — specific ones chosen
by the kernel community) and continues backporting bugfixes to them for **years**, specifically for
distributions, embedded systems, and enterprises that need a long-lived, stable target to build on rather than
constantly rebasing onto new mainline releases.

## Worked example: real, current release data, not a snapshot from training data

```text
$ curl -s https://www.kernel.org/releases.json | python3 -c "
import json, sys
for r in json.load(sys.stdin)['releases']:
    if r['moniker'] in ('mainline','stable','longterm'):
        print(r['moniker'], r['version'], r['released']['isodate'])
"
mainline  7.3      2026-10-18
stable    7.2.12   2026-10-21
longterm  6.18.58  2026-10-21
longterm  6.12.114 2026-10-21
longterm  6.6.160  2026-10-21
longterm  6.1.190  2026-10-15
longterm  5.15.223 2026-10-15
longterm  5.10.272 2026-10-15
```

(Real data, fetched live from kernel.org at the time this lesson was written — not recalled from memory, and
guaranteed to look different by the time you read this, which is itself the point.) Notice **six** different
longterm lines actively receiving updates simultaneously, spanning from `5.10` through `6.18` — this is normal;
LTS kernels have long support windows specifically so a distro or device shipped years ago can keep receiving
security patches without a disruptive jump to a much newer kernel. The gap between mainline (`7.3`) and the
newest longterm line (`6.18.58`) is also normal: a kernel doesn't need to be the newest mainline release to be
fully supported — LTS designation is a deliberate choice made for specific releases, not every one.

## How It Actually Works

A kernel's **version number** itself encodes which patches it has, but not which support line it belongs to —
you have to cross-reference against kernel.org's (or your distro's) current release data to know whether a given
version is still receiving security fixes, which is exactly why checking a live source matters more than
remembering a number. Distributions add their own layer on top: Ubuntu's kernel version strings (like this
course's lab VM's own `7.0.0-34-generic`, from `uname -r` in Level 1) combine an upstream base version with
Ubuntu's own ABI build number — distros frequently **backport** specific newer features or hardware support into
an otherwise-older base kernel, meaning the version number alone doesn't tell you everything a distro kernel
actually contains; the distro's own kernel changelog is the authoritative source for that, not the raw version
string.

This is also why "just run the newest kernel" isn't automatically correct advice: mainline and short-lived
stable releases have had far less real-world testing time than a mature LTS release that's been running on
millions of machines for months or years — for a production server, a well-supported LTS line is very often the
*more* stable choice precisely because it's not the newest, not despite it.

## Common mistakes

- **Trusting a remembered or trained-on "current kernel version" instead of checking a live source.** As this
  lesson demonstrates by fetching real-time data, kernel releases happen on an ongoing cadence — any specific
  version number you've memorized is a snapshot that ages, sometimes within weeks.
- **Assuming a distro's kernel version number maps directly to kernel.org's release lines.** Distro kernels are
  frequently patched and backported independently of upstream naming — check your specific distro's kernel
  changelog, not just the bare `uname -r` number, before concluding what security fixes it does or doesn't have.
- **Chasing mainline for a production system "to get the latest features."** Mainline and stable lines are
  retired relatively quickly and have had the least cumulative real-world testing — an LTS line is usually the
  better fit unless a specific feature or hardware-support need genuinely requires something newer.

## Exercise

Run `curl -s https://www.kernel.org/releases.json` yourself (or visit kernel.org directly) and compare the
current mainline, stable, and longterm versions against what this lesson showed — note how much has changed.
Then check your own machine's kernel with `uname -r` and look up, in your distro's own documentation or
changelog, which upstream longterm line (if any) it's actually built from.
