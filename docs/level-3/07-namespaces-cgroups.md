---
description: "What a PID namespace actually isolates, shown live with unshare, plus the real cgroup v2 hierarchy every process already belongs to."
---

# 07 · Namespaces & Cgroups: The Building Blocks of Containers

"A container is a lightweight VM" is a useful lie for getting started and a genuinely misleading one the moment
you need to debug something. A container is a normal Linux process, running on the same kernel as everything
else on the host, made to *look* isolated by two independent kernel mechanisms: **namespaces** (what you can
see) and **cgroups** (what you can use). This lesson builds the isolation half by hand with `unshare`, no
container runtime involved at all.

## Namespaces: isolating what a process can see

A **namespace** wraps one specific kind of global kernel resource so that a process inside it sees its own private
instance instead of the real, system-wide one. Linux has several: **PID** (a private process-ID space, so a
process inside can be "PID 1" in its own view while being some unrelated PID on the host), **mount** (a private
view of what's mounted where), **network** (its own interfaces, routing table, and port space), **UTS** (its own
hostname — the exact thing Level 1's chroot project showed was *not* isolated by plain `chroot`), **user** (its
own UID/GID mapping, so "root" inside can be an unprivileged user outside), **IPC**, and **cgroup** (a private
view of its own cgroup hierarchy).

## Worked example: a real, isolated PID namespace, built by hand

```text
$ sudo unshare --pid --mount-proc --fork bash -c "
    echo inside namespace, bash PID: \$\$
    sleep 2 &
    ps aux
    wait
"
inside namespace, bash PID: 1
USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root           1  0.0  0.0   8144  3244 ?        S    16:28   0:00 bash -c ...
root           2  0.0  0.1  17040  6212 ?        R    16:28   0:00 sleep 2
root           3  0.0  0.0   9736  3552 ?        R    16:28   0:00 ps aux
```

(Real output from this course's lab VM.) `bash`, inside this new PID namespace, is genuinely, literally **PID 1**
— not a cosmetic relabeling, but what `getpid()` actually returns to it. `ps aux`, which reads the freshly
mounted `/proc` this namespace provides (`--mount-proc` is what makes that possible — without it, `/proc` would
still show the *host's* process table through the mount namespace, which would break the illusion immediately),
sees **exactly three processes total**: itself, the shell, and the `sleep` it backgrounded — not the dozens or
hundreds of real processes running on the actual host at the same moment. This is the entire mechanism: the
kernel is running the same real scheduler, the same real processes, on the same real hardware — it has simply
restricted what this one process tree can *see* through the PID namespace's private numbering and `/proc` view.

## Worked example: the cgroup every process is already in

```text
$ mount | grep cgroup2
cgroup2 on /sys/fs/cgroup type cgroup2 (rw,nosuid,nodev,noexec,relatime,nsdelegate,memory_recursiveprot,...)

$ cat /proc/self/cgroup
0::/user.slice/user-501.slice/session-6.scope
```

(Real output.) Every process on a modern Linux system is already assigned to a cgroup, whether or not anyone set
a limit on it — this ordinary interactive shell lives in `user.slice/user-501.slice/session-6.scope`, a path
`systemd` (Lesson 6, Level 2) created automatically for this login session. **Cgroups** (control groups) are the
*other* half of the isolation story: where namespaces control visibility, cgroups control and account for actual
resource consumption — CPU shares, memory limits (exactly what produced the real OOM kill in Level 2, Lesson 3),
I/O bandwidth, and process counts — for whatever set of processes is placed in a given cgroup, regardless of
whether those processes can even see each other through a namespace.

## How It Actually Works

Namespaces and cgroups are **orthogonal**: a process can be namespace-isolated without any cgroup limits at all
(as in this lesson's `unshare` demo — nothing stopped that bash process from using unlimited CPU or memory, it
just couldn't *see* the rest of the system), or cgroup-limited without any namespace isolation (a process capped
at 100 MB of memory that can still see and signal every other process on the host). A real container runtime
(Docker, containerd, Podman) combines **several** namespace types plus a cgroup, plus usually some combination of
an LSM profile (Level 3, Lesson 6) and a restricted set of allowed syscalls (`seccomp`) — none of which is a
single "container" primitive in the kernel; "container" is a userspace word for a particular, common combination
of these genuinely separate, independently-usable kernel mechanisms. This is exactly why `unshare` and
`cgroup`-management tools can build a working, real isolation boundary with no container software installed at
all, as this lesson just did.

User namespaces deserve a specific mention: by mapping a range of host UIDs to a different range inside the
namespace, a process can be "root" (UID 0) *inside* its namespace while mapping to a thoroughly unprivileged UID
on the host — meaning a compromised "root" process inside a well-configured container often cannot actually do
anything privileged on the real host at all, a meaningfully different security posture from running as real root
everywhere.

## Common mistakes

- **Treating `unshare`'s PID namespace isolation as a complete security sandbox on its own.** As shown above, it
  controls *visibility*, not resource usage or privilege — a process in a PID namespace with no cgroup limits and
  no dropped capabilities can still consume unlimited host CPU/memory and, depending on what other namespaces are
  (or aren't) also unshared, potentially still affect the host in other ways.
- **Forgetting `--mount-proc` when creating a new PID namespace.** Without it, tools like `ps` inside the
  namespace read the *host's* `/proc` through the inherited mount namespace and show misleading, host-wide
  process information that doesn't match the namespace's actual isolated view.
- **Assuming every process's cgroup membership implies an active limit.** As the real `/proc/self/cgroup` output
  above shows, being assigned to a cgroup path is universal and automatic under `systemd`; whether that cgroup
  actually enforces a CPU/memory ceiling depends on whether limits were explicitly configured for it.

## Exercise

Run this lesson's exact `unshare --pid --mount-proc --fork` command yourself and confirm your own shell reports
PID 1 inside it. Then, from a *second* terminal on the same host, find that same bash process's real PID with
`ps -ef | grep unshare` and confirm it's a large, ordinary-looking PID from the host's perspective — proving the
"PID 1" from inside is a namespace-local view, not a system-wide fact.
