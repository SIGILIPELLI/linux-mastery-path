---
description: "Project: combine unshare namespaces and a real cgroup memory limit by hand into something that behaves like a small container, no runtime involved."
---

# 10 · Project: Build a Container From Namespaces and Cgroups

Lessons 7 and 8 covered namespaces, cgroups, and kernel tuning separately. This project combines the first two
by hand — no Docker, no Podman, no container runtime at all — into a process that is genuinely isolated (its own
hostname, its own process tree) and genuinely resource-limited (a real memory ceiling, really enforced by the
kernel), which is the complete, if minimal, definition of what a container actually is underneath the tooling.

## Building it

```bash
sudo mkdir -p /sys/fs/cgroup/minicontainer
echo "50M" | sudo tee /sys/fs/cgroup/minicontainer/memory.max

sudo unshare --pid --mount-proc --uts --fork bash -c '
  hostname minicontainer
  echo my hostname: $(hostname)
  echo my pid: $$
  echo $$ | sudo tee /sys/fs/cgroup/minicontainer/cgroup.procs > /dev/null
  ps aux
  python3 -c "
a = []
for i in range(200):
    a.append(bytearray(1024*1024))
"
'
```

`--uts` adds hostname isolation to the PID/mount isolation from Lesson 7's project; `memory.max` on a freshly
created cgroup v2 directory sets a hard memory ceiling; writing the shell's own PID into that cgroup's
`cgroup.procs` moves it (and everything it subsequently spawns) into the limited group.

## What actually happened

```text
$ echo "50M" | sudo tee /sys/fs/cgroup/minicontainer/memory.max
50M

$ sudo unshare --pid --mount-proc --uts --fork bash -c '...'
my hostname: minicontainer
my pid: 1
52428800
USER   PID %CPU %MEM COMMAND
root     1  0.0  0.0 bash -c ...
root     9  0.0  0.0 ps aux
Killed

$ hostname
lima-linuxlab

$ sudo dmesg | tail -n3
Memory cgroup stats for /minicontainer:
anon 52150272
oom-kill:constraint=CONSTRAINT_MEMCG,...,cpuset=minicontainer,oom_memcg=/minicontainer,task_memcg=/minicontainer,
  task=python3,pid=267454,uid=0
Memory cgroup out of memory: Killed process 267454 (python3) total-vm:66744kB, anon-rss:50928kB, ...
```

(Real output from this course's lab VM — this is a genuine OOM kill inside a hand-built cgroup, not a simulated
one.) Every piece of isolation and limiting worked exactly as specified: `hostname` *inside* the namespace reports
`minicontainer`, while the real host's `hostname`, checked immediately afterward from outside, still reports
`lima-linuxlab` — the UTS namespace genuinely isolated it, unlike Level 1's plain `chroot` project, which could
**not** isolate hostname at all. `cat .../memory.max` confirms the kernel stored the limit as exactly `52428800`
bytes (50 × 1024 × 1024, the binary-megabyte interpretation of "50M"). And the Python allocation loop — which, if
unlimited, would have run to completion printing nothing unusual — instead got **killed outright** partway
through, with no Python exception ever printed (`Killed` is the shell reporting a `SIGKILL`, not a caught
`MemoryError`), and `dmesg` confirms exactly why: `CONSTRAINT_MEMCG`, `cpuset=minicontainer`,
`oom_memcg=/minicontainer` — the real kernel OOM killer, acting specifically within the cgroup this project
created, at just over the 50 MB ceiling (`anon-rss:50928kB`).

## How It Actually Works

This project is deliberately the minimum viable version of what `runc` (the low-level runtime underneath Docker
and most other container tools) actually does when it starts a container: create a set of namespaces for the new
process (this project used PID, mount, and UTS; a full container runtime typically also adds network, IPC, and
user namespaces), place the process into a cgroup with resource limits configured, and — in a production runtime
—additionally apply an LSM profile (Level 3, Lesson 6) and a seccomp syscall filter, neither of which this
project bothered with, which is exactly why this mini-container is a real but genuinely minimal and
**not security-hardened** example: it demonstrates the mechanism, not a production-safe isolation boundary.

The OOM kill happening *inside the cgroup specifically*, rather than threatening the whole host's memory, is the
entire point of cgroup memory accounting: the kernel tracks this cgroup's total memory usage as its own pool,
separate from system-wide memory pressure, and enforces the 50 MB ceiling against that pool specifically — the
rest of the host (including the shell that launched `unshare` itself, living in a different cgroup) was never at
risk, exactly as Level 2 Lesson 3's standalone OOM demo showed with `systemd-run --scope`, just built here by
hand against the raw cgroup v2 filesystem interface instead of through `systemd`'s convenience wrapper.

## Common mistakes

- **Forgetting this project's limits are not a security boundary.** No LSM profile, no seccomp filter, and
  (without `--user`, not used here) no user namespace means the process is still fully privileged within the
  isolation it does have — exactly the caveat from Lesson 7, repeated here because it's easy to forget once
  something this convincingly "container-like" is working.
- **Writing the PID into `cgroup.procs` before the process exists**, or into the wrong cgroup path entirely — a
  typo here silently leaves the process in its *original* cgroup with no limit applied at all, and nothing about
  the shell session itself will look wrong until the memory limit you expected simply doesn't trigger.
- **Expecting a clean `MemoryError` or similar Python-level signal from a cgroup OOM kill.** As shown here,
  `SIGKILL` gives the process zero chance to catch anything — any cleanup logic, log flushing, or graceful
  shutdown code a real application might have never runs.

## Exercise

Build this project yourself with a smaller limit (`memory.max` of `20M`) and a workload that allocates faster, and
confirm via `dmesg` that the resulting kill shows `oom_memcg=/<your cgroup path>` matching what you created —
not the system-wide OOM path from Level 2's standalone demo. Then repeat the hostname check from both inside and
outside the namespace, and explain in your own words why the host's hostname was never at risk, tying the
explanation back to what a UTS namespace specifically isolates.
