---
description: "Mandatory access control explained through real AppArmor confinement (a confined dig process vs an unconfined sshd), plus SELinux's labeling model."
---

# 06 · Linux Security Modules: SELinux vs AppArmor

Standard Unix permissions (Level 1) answer "can this *user* read this file." A **Linux Security Module (LSM)**
answers a different question entirely: "can this *specific program*, regardless of which user runs it, do this
specific thing" — a layer of **mandatory access control** that applies on top of, and independent from, the
owner/group/other model, enforced even for root.

## Two real LSMs, two different philosophies

**AppArmor** (Ubuntu/Debian's default) is **path-based**: profiles are written per-executable-path, naming
exactly which files, capabilities, and network operations that program may use. **SELinux** (Red
Hat/Fedora/CentOS's default) is **label-based**: every file, process, and socket gets a security **context**
(user:role:type:level), and policy rules are written in terms of which types may interact with which other types
— a more expressive but also more complex model, which is part of why AppArmor has a reputation as the "easier"
of the two and SELinux as the more thorough but harder-to-debug one.

## Worked example: real AppArmor confinement caught in the act

```text
$ sudo aa-status
apparmor module is loaded.
180 profiles are loaded.
103 profiles are in enforce mode.
2 profiles are in complain mode.
3 processes are unconfined but have a profile defined.

$ for p in $(pgrep -f sshd); do echo "pid $p: $(cat /proc/$p/attr/current)"; done
pid 2181: unconfined
pid 2188: unconfined

$ dig +short github.com &
$ cat /proc/$(pgrep dig)/attr/current
dig (enforce)
```

(Real output from this course's lab VM — AppArmor is the active LSM here, since this is Ubuntu; this is not a
staged example.) `aa-status` reports a genuinely active, enforcing AppArmor: 180 profiles loaded, 103 actually
enforcing (not just logging). Yet checking `sshd`'s own running processes via `/proc/<pid>/attr/current` (the
per-process file the kernel exposes for exactly this purpose) shows `unconfined` — this minimal server image has
a profile loaded for several binaries but `sshd` itself isn't one of them on this particular system, which is a
realistic, honest result: having *a* profile loaded for *some* binaries doesn't mean *every* running process is
confined. Running `dig` (which does have an active profile) immediately shows the difference: its own
`/proc/<pid>/attr/current` reports `dig (enforce)` — the kernel is actively restricting what that one process can
do, in real time, for the duration it runs.

## How It Actually Works

Both AppArmor and SELinux are implemented as **LSM hooks**: the kernel's security module framework calls out to
the active LSM at specific decision points (opening a file, binding a socket, using a capability) *in addition
to* the normal DAC (discretionary access control — the standard permission bits) checks that already happen at
those same points. This is why LSM restrictions are described as "mandatory" — even a process running as root,
which bypasses virtually all DAC checks, still has to pass the LSM's rules, which is precisely the point: without
an LSM, root compromise of one service (a web server with a code-execution bug, say) is root compromise of the
*entire machine*; with a tight AppArmor or SELinux profile around that service, a compromised, still-root-owned
process can still be confined to only the files, capabilities, and operations its profile explicitly allows,
containing the blast radius even after the application-level compromise already happened.

AppArmor's path-based model means a profile like the one for `chronyd` directly enumerates file paths and
capabilities (`capability net_admin`, access to `/run/chrony`) — readable and auditable by inspecting one text
file per program. SELinux's label-based model instead asks "what *type* is this file, what *type* is this
process, does policy allow that type pair to interact this way" — which scales better to complex systems (a new
file automatically inherits sensible labeling rules rather than needing a brand-new path-based rule) but requires
understanding the type system itself, not just reading one profile, to reason about a given interaction.

## Common mistakes

- **Disabling the LSM entirely ("just set SELinux to permissive" / "just disable AppArmor") to make an
  application error go away**, rather than diagnosing which specific rule is blocking it. This removes a whole
  layer of defense system-wide for one application's convenience — `aa-logprof`/`audit2allow`-style tooling exists
  specifically to generate a correct, narrow policy addition instead.
- **Assuming "the LSM is enabled" means every process is confined.** As this lesson's real output shows directly,
  a profile being loaded and enforcing for *some* binaries says nothing about processes with no matching profile
  at all — check the specific process, not just the subsystem's overall status.
- **Confusing "enforce" and "complain"/"permissive" modes.** Both log policy violations, but only enforce mode
  actually blocks the disallowed action — a profile left in complain/permissive mode after testing provides
  visibility but zero actual protection, a common and easy-to-miss leftover from initial policy development.

## Exercise

Run `aa-status` (Ubuntu/Debian) or `sestatus` (RHEL/Fedora) on a Linux machine, and check `/proc/<pid>/attr/current`
for three different running processes — pick one you'd expect to be confined (a daemon with a well-known profile)
and one you wouldn't (your own interactive shell). Confirm your expectations against the real output, and for any
surprise, investigate whether a profile exists for that binary at all before assuming the LSM itself is broken.
