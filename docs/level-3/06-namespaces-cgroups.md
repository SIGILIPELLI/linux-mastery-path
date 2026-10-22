---
description: "How containers work: the eight namespace types and cgroup v2 limits for CPU, memory and pids, with unshare examples and a tested parser."
---

# 06 · Namespaces & cgroups: How Containers Work

A container is not a lightweight virtual machine. It's an ordinary Linux process (or tree of processes) whose view of the system is restricted by **namespaces** and whose resource use is restricted by **cgroups**, usually with extra filters from capabilities, seccomp and mandatory access control (Lesson 07). Once you see this, container
behaviour, the "OOM-killed with plenty of host memory" mystery, and container security all follow.

!!! note "What was run"
    Namespaces and cgroups are Linux kernel features and macOS lacks them, so **`unshare`, `nsenter`, `systemd-run` and cgroup files were not run**. Facts are from `namespaces(7)` and `cgroups(7)` (man7.org) and the kernel's cgroup v2 documentation (docs.kernel.org), read October 2026. The only code I ran is a **cgroup file parser, tested on
    fixtures I wrote** in the documented formats (the parsing is real, the numbers are invented). See Level 1 · Lesson 01.

## Namespaces: what a process can see

Per `namespaces(7)`: "A namespace wraps a global system resource in an abstraction that makes it appear to the processes within the namespace that they have their own isolated instance of the global resource." Changes inside are invisible outside. The types on Linux:

| Namespace | Flag | Isolates |
|---|---|---|
| **PID** | `CLONE_NEWPID` | Process IDs (the first process inside is PID 1) |
| **Mount** | `CLONE_NEWNS` | Mount points (a private filesystem tree; with `pivot_root`, a container's own root) |
| **Network** | `CLONE_NEWNET` | Network devices, IP addresses, routing tables, ports, firewall rules |
| **UTS** | `CLONE_NEWUTS` | Hostname and NIS domain name |
| **IPC** | `CLONE_NEWIPC` | System V IPC and POSIX message queues |
| **User** | `CLONE_NEWUSER` | User and group IDs (map "root" inside to an unprivileged user outside) |
| **Cgroup** | `CLONE_NEWCGROUP` | The cgroup root directory a process sees |
| **Time** | `CLONE_NEWTIME` | Boot and monotonic clocks |

They're created with `clone(2)` flags or `unshare(2)`, joined with `setns(2)`, and visible as links in `/proc/<pid>/ns/`. Creating most types normally requires `CAP_SYS_ADMIN` (user namespaces are the way unprivileged users get a "root" inside a sandbox).

### Try it (Linux; not run)

```bash
sudo unshare --pid --fork --mount-proc --uts --net bash     # new PID, UTS, network (and a fresh /proc mount)
hostname demo-box         # changes the hostname only inside
ps aux                    # only processes in this PID namespace; bash is PID 1
ip addr                   # only a down loopback interface: an isolated network stack
exit
ls -l /proc/$$/ns         # namespace identity links, e.g. net:[4026531840]
sudo nsenter --target <pid> --net ip addr   # run a command inside another process's network namespace
```

Two processes are in the same namespace if the inode number in their `/proc/<pid>/ns/net` link is the same: that's how you find out what a container shares with the host. `docker run --network=host` simply doesn't create a new network namespace; `--pid=host` doesn't create a PID namespace, which is why those flags are security-relevant.

## cgroups: how much a process may use

**Control groups** organise processes into a hierarchy and apply resource accounting and limits via *controllers*. Modern distributions use **cgroup v2**, a single unified hierarchy mounted at `/sys/fs/cgroup`. A group is a directory; its interface files control it. A process belongs to the group whose `cgroup.procs` lists its PID
(`/proc/<pid>/cgroup` shows the path).

| File | Meaning (kernel docs) |
|---|---|
| `cpu.weight` | Relative share under contention; default 100, range 1 to 10000 |
| `cpu.max` | Hard bandwidth limit: `$MAX $PERIOD` in microseconds; default `max 100000` (unlimited) |
| `memory.max` | Hard limit; "if a cgroup's memory usage reaches this limit and can't be reduced, the OOM killer is invoked in the cgroup" |
| `memory.high` | Throttle limit: above it processes are slowed and put under reclaim pressure; "going over the high limit never invokes the OOM killer" |
| `pids.max` | Maximum number of processes (stops fork bombs) |
| `io.max`, `io.weight` | Block I/O limits and weights |
| `memory.events`, `memory.current`, `cpu.stat`, `pids.current` | Accounting and events |
| `cgroup.procs`, `cgroup.subtree_control` | Membership and which controllers are enabled for children |

The cgroups v2 "no internal processes" rule says a group that delegates controllers to children can't itself contain processes (with some relaxations): processes live in leaf groups. systemd, Docker and Kubernetes all manage this tree for you; each systemd service gets its own cgroup (Level 2 · 02), so
`systemctl set-property myapp.service MemoryMax=500M CPUQuota=150% TasksMax=200` writes `memory.max`, `cpu.max` and `pids.max`.

### Reading cgroup files with a parser (run on fixtures)

```python
def cpu_limit(cpu_max_text):
    quota, period = cpu_max_text.split()
    return None if quota == "max" else int(quota) / int(period)

def parse_flat_keyed(text):
    return {k: int(v) for k, v in (line.split() for line in text.strip().splitlines())}

def proc_cgroup_path(text):
    for line in text.strip().splitlines():
        hid, controllers, path = line.split(":", 2)
        if hid == "0" and controllers == "": return path
```

Run (macOS, Python; fixtures hand-written in the documented formats):

```text
cpu_limit("max 100000")    -> None       (unlimited)
cpu_limit("100000 100000") -> 1.0        (one CPU)
cpu_limit("150000 100000") -> 1.5        cpu_limit("50000 100000") -> 0.5       cpu_limit("800000 100000") -> 8.0
memory.events fixture "low 0 / high 12 / max 3 / oom 1 / oom_kill 1 / oom_group_kill 0" -> {'low': 0, 'high': 12, 'max': 3, 'oom': 1, 'oom_kill': 1, 'oom_group_kill': 0}; oom_kill > 0 → True
proc_cgroup_path("0::/system.slice/myapp.service") -> /system.slice/myapp.service
```

### CPU limits throttle; they don't allocate

A `cpu.max` of `150000 100000` means the group may use 150 ms of CPU time in every 100 ms period, i.e. 1.5 CPUs. If four busy threads run in it, they *want* 400 ms per period; the quota allows 150, so together they run for a total of 150 ms then are **throttled** until the next period: each thread gets about 37.5 ms
of every 100 ms, so it sits stopped about 62 ms per period (my arithmetic from the definition). Throttling shows up as latency spikes at low average CPU use, and `cpu.stat` fields `nr_throttled` and `throttled_usec` reveal it. This is why a service with a CPU limit of 1.0 can have bad tail latency even when "CPU use is only 40%".
`cpu.weight`, by contrast, only matters when CPUs are contended.

### Memory limits and OOM kills

`memory.max` is a wall: crossing it triggers reclaim and, if that fails, an OOM kill **inside that cgroup** regardless of free host memory (Lesson 02). `memory.events` counts the occurrences (`oom_kill`), and a killed process exits with status 137. `memory.high` is a softer brake that slows the group instead of killing it. The page cache of the container's files counts toward its
memory: a service that reads lots of files can approach its limit through cache alone, usually harmlessly because clean cache is reclaimable, but the numbers can alarm you.

## Putting it together: what `docker run` does (conceptually)

1. Unpack the image's layers into a filesystem (overlayfs) and make it the new **mount namespace's** root.
2. Create PID, network, UTS, IPC (and optionally user) namespaces; connect the network namespace to the host with a virtual Ethernet pair and a bridge.
3. Create a cgroup with the requested limits (`--memory`, `--cpus`) and move the process into it.
4. Drop capabilities, apply a seccomp filter and an AppArmor/SELinux profile (Lesson 07).
5. `exec` the container's entrypoint as PID 1 of the new PID namespace.

Everything is visible from the host: container processes show up in the host's `ps` with different PIDs, and `nsenter` can enter their namespaces. **The kernel is shared**: a kernel vulnerability affects every container, and a container cannot run a different kernel version than the host. The usual caveats of PID 1 apply: PID 1 must reap zombies and
handle signals (a naive shell script as PID 1 ignores SIGTERM; use `tini` or `docker run --init`).

## How It Actually Works

Each task struct holds pointers to its namespaces (`nsproxy`) and to its cgroup membership. Kernel subsystems consult the namespace pointer whenever they look up a global thing: the PID allocator uses the PID namespace's table, the network stack uses the network namespace's devices and routing, path resolution uses the mount namespace's tree, and `uname` reads the UTS namespace's hostname. Namespaces are reference-counted
and live as long as a process or an open file descriptor (or bind mount) refers to them. cgroup controllers hook the same events the kernel already handles: the scheduler charges CPU time to the task's group and enforces quota with a per-group timer; the memory allocator charges page allocations to a group's counter and reclaims or kills when the limit is hit; the `fork` path checks `pids.max`.

## Common mistakes

- **Calling containers "VMs"** and expecting kernel isolation.
- **Memory limits set to the average**, causing OOM kills at peaks.
- **CPU limits causing throttling latency** (consider requests/weights without hard limits for latency-sensitive services).
- **Running as root inside the container with host namespaces or `--privileged`.**
- **PID 1 that doesn't reap zombies or handle SIGTERM.**
- **Monitoring host free memory** while the container is at its cgroup limit.
- **Assuming `/proc` and `top` inside a container show container limits** (many tools read host-wide values, e.g. CPU count and memory totals, unless made cgroup-aware).

## Exercise

1. On a Linux VM, use `systemd-run --scope -p MemoryMax=100M -p TasksMax=20 bash` and try to allocate 200 MB and fork 50 processes; read `memory.events` and `pids.events` afterwards.
2. Use `unshare` to create a PID+mount namespace, mount `/proc`, and show that `ps` sees only your processes; then find the same process from the host with its host PID.
3. Create a cgroup by hand under `/sys/fs/cgroup`, set `cpu.max` to `50000 100000`, run a busy loop in it, and confirm with `top` that it uses ~50% of one CPU and `cpu.stat` shows throttling.
4. Compare `/proc/self/ns/*` inside and outside a container to list exactly which namespaces it shares with the host.
