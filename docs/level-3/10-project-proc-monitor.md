---
description: "Level 3 project: a /proc monitor whose proc root is a parameter, tested with fabricated /proc trees for CPU, memory, load and zombies."
---

# 10 · Project — A /proc-Based Monitor with Tests

Build a small monitoring script that reads Linux `/proc`, computes health indicators, raises alerts, and exits non-zero when something needs attention. The key design decision, taken from Lesson 03: the **proc root is a parameter**, so the same code runs against the real `/proc` on a server or against a fabricated directory
tree in tests. That is how you can develop, test and demonstrate a Linux-specific tool on a Mac.

!!! note "What was run"
    The monitor and its **8 pytest tests were run on macOS**, against **fixture `/proc` trees that I generated in the documented file formats** (`proc(5)`, `proc_meminfo(5)`, `proc_loadavg(5)`; Lesson 03). **It was never run against a real Linux `/proc`**, so there may be differences on real systems (extra fields, permissions, races) that these fixtures don't
    capture. All numbers shown are invented. See Level 1 · Lesson 01.

## Requirements

1. Compute CPU utilisation as a **delta between two samples** of `/proc/stat` (not a single reading).
2. Report memory as `MemAvailable` percentage, swap in use, load per CPU, runnable tasks.
3. List the top three processes by resident memory and detect zombies and processes with many open files.
4. Raise `WARN`/`CRIT` alerts with simple thresholds; exit `1` if any alert is present.
5. Tolerate processes that disappear while being read (normal on a live system).
6. Be testable without Linux.

## procmon.py

```python
"""A small /proc-based monitor. The proc root is a parameter, so it can run against a real /proc ("/proc") or a fixture tree.
Formats follow proc(5), proc_meminfo(5) and proc_loadavg(5). Exit status: 0 OK, 1 warning/critical alerts present."""
import json, os, re, sys, time
from pathlib import Path

def read(p): return Path(p).read_text()

def meminfo(root):
    out = {}
    for line in read(f"{root}/meminfo").splitlines():
        m = re.match(r"(\w[\w()]*):\s+(\d+)", line)
        if m: out[m.group(1)] = int(m.group(2))
    return out

def loadavg(root):
    a, b, c, runq, _ = read(f"{root}/loadavg").split()
    return float(a), float(b), float(c), int(runq.split("/")[0])

def cpu_jiffies(root):
    f = list(map(int, read(f"{root}/stat").splitlines()[0].split()[1:]))
    f += [0] * (8 - len(f))
    return sum(f[:8]), f[3] + f[4]                       # total, idle+iowait

def ncpus(root):
    return sum(1 for line in read(f"{root}/stat").splitlines() if re.match(r"cpu\d+\s", line)) or 1

def processes(root):
    procs = []
    for d in Path(root).iterdir():
        if not d.name.isdigit(): continue
        try:
            st = {}
            for line in (d / "status").read_text().splitlines():
                k, _, v = line.partition(":"); st[k] = v.strip()
            fds = len(list((d / "fd").iterdir())) if (d / "fd").exists() else 0
            procs.append({"pid": int(d.name), "name": st.get("Name", "?"), "state": st.get("State", "?")[:1],
                          "rss_kb": int(st.get("VmRSS", "0 kB").split()[0]), "fds": fds})
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue                                       # the process vanished or is unreadable: normal on a live system
    return procs

def snapshot(root, interval=0.0, sleeper=time.sleep):
    t0, i0 = cpu_jiffies(root)
    if interval: sleeper(interval)
    t1, i1 = cpu_jiffies(root)
    cpu = 100.0 * (1 - (i1 - i0) / (t1 - t0)) if t1 > t0 else None
    mi = meminfo(root); l1, l5, l15, runnable = loadavg(root); n = ncpus(root)
    ps = processes(root)
    swap_used = mi.get("SwapTotal", 0) - mi.get("SwapFree", 0)
    return {"cpus": n, "cpu_percent": cpu, "load": [l1, l5, l15], "load_per_cpu": l1 / n, "runnable": runnable,
            "mem_available_pct": 100.0 * mi["MemAvailable"] / mi["MemTotal"], "swap_used_kb": swap_used,
            "top_rss": sorted(ps, key=lambda p: -p["rss_kb"])[:3], "zombies": [p["pid"] for p in ps if p["state"] == "Z"],
            "max_fds": max((p["fds"] for p in ps), default=0)}

def alerts(s, fd_limit=1000):
    out = []
    if s["load_per_cpu"] > 1.5: out.append(("CRIT", f"load per CPU {s['load_per_cpu']:.2f} > 1.5"))
    elif s["load_per_cpu"] > 1.0: out.append(("WARN", f"load per CPU {s['load_per_cpu']:.2f} > 1.0"))
    if s["cpu_percent"] is not None and s["cpu_percent"] > 90: out.append(("WARN", f"CPU {s['cpu_percent']:.0f}% busy over the interval"))
    if s["mem_available_pct"] < 10: out.append(("CRIT", f"only {s['mem_available_pct']:.1f}% memory available"))
    elif s["mem_available_pct"] < 20: out.append(("WARN", f"{s['mem_available_pct']:.1f}% memory available"))
    if s["swap_used_kb"] > 0 and s["mem_available_pct"] < 20: out.append(("WARN", f"swap in use ({s['swap_used_kb']} kB) while memory is tight"))
    if s["zombies"]: out.append(("WARN", f"zombie processes: {s['zombies']}"))
    if s["max_fds"] > fd_limit * 0.8: out.append(("WARN", f"a process has {s['max_fds']} open files (limit assumed {fd_limit})"))
    return out

if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "/proc"
    snap = snapshot(root, interval=1.0 if root == "/proc" else 0.0)
    al = alerts(snap)
    print(json.dumps(snap, indent=2, default=str)); [print(f"[{sev}] {msg}") for sev, msg in al]
    sys.exit(1 if al else 0)
```

## The fixture builder

```python
"""Build a fake /proc tree in documented formats. Values are invented."""
from pathlib import Path
def build(root, *, mem_avail=12288000, mem_total=16384000, load="0.74 0.58 0.52 2/432 98712", stat1=None, procs=None, swap_free=2097152, ncpu=4):
    r = Path(root); r.mkdir(parents=True, exist_ok=True)
    (r / "meminfo").write_text(f"MemTotal:       {mem_total} kB\nMemFree:          412000 kB\nMemAvailable:   {mem_avail} kB\nSwapTotal:       2097152 kB\nSwapFree:        {swap_free} kB\n")
    (r / "loadavg").write_text(load + "\n")
    cpus = "".join(f"cpu{i} 250 0 125 2000 25 0 0 0\n" for i in range(ncpu))
    (r / "stat").write_text(stat1 or ("cpu  1000 0 500 8000 100 0 0 0\n" + cpus))
    for pid, name, state, rss, nfd in (procs or [(1, "systemd", "S", 11000, 20), (812, "sshd", "S", 7000, 8), (4242, "java", "S", 2048000, 120)]):
        d = r / str(pid); (d / "fd").mkdir(parents=True, exist_ok=True)
        (d / "status").write_text(f"Name:\t{name}\nState:\t{state} (sleeping)\nPid:\t{pid}\nVmRSS:\t{rss} kB\n")
        for i in range(nfd): (d / "fd" / str(i)).write_text("")
```

## Tests

```python
import procmon, make_fixture
def snap(tmp_path, interval=0.0, **kw):
    make_fixture.build(tmp_path, **kw); return procmon.snapshot(str(tmp_path))
def msgs(s, **kw): return [m for _, m in procmon.alerts(s, **kw)]

def test_healthy_has_no_alerts(tmp_path):
    s = snap(tmp_path); assert s["cpus"] == 4 and abs(s["mem_available_pct"] - 75.0) < 0.01 and procmon.alerts(s) == []
def test_top_rss_sorted(tmp_path):
    s = snap(tmp_path); assert [p["name"] for p in s["top_rss"]] == ["java", "systemd", "sshd"]
def test_high_load(tmp_path):
    s = snap(tmp_path, load="7.00 5.00 3.00 9/400 1"); assert any("CRIT" == sev for sev, _ in procmon.alerts(s))
def test_low_memory_and_swap(tmp_path):
    s = snap(tmp_path, mem_avail=1000000, swap_free=1000000); m = msgs(s); assert any("memory available" in x for x in m) and any("swap in use" in x for x in m)
def test_zombie_detected(tmp_path):
    s = snap(tmp_path, procs=[(1, "init", "S", 100, 3), (77, "defunct", "Z", 0, 0)]); assert s["zombies"] == [77] and any("zombie" in x for x in msgs(s))
def test_many_fds(tmp_path):
    s = snap(tmp_path, procs=[(1, "init", "S", 100, 3), (9, "leaky", "S", 100, 900)]); assert any("open files" in x for x in msgs(s))
def test_cpu_percent_between_samples(tmp_path):
    make_fixture.build(tmp_path)
    calls = []
    def sleeper(_):
        (tmp_path / "stat").write_text("cpu  1300 0 600 8500 150 0 0 0\ncpu0 1 0 0 1 0 0 0 0\ncpu1 1 0 0 1 0 0 0 0\ncpu2 1 0 0 1 0 0 0 0\ncpu3 1 0 0 1 0 0 0 0\n"); calls.append(1)
    s = procmon.snapshot(str(tmp_path), interval=1.0, sleeper=sleeper)
    assert calls and abs(s["cpu_percent"] - 42.105) < 0.01
def test_vanishing_process_ignored(tmp_path):
    make_fixture.build(tmp_path); (tmp_path / "555").mkdir()                    # a directory with no status file, as if the process just exited
    assert 555 not in [p["pid"] for p in procmon.processes(str(tmp_path))]
```

```text
8 passed in 0.18s
```

The tests cover: a healthy host gives no alerts; the top-RSS list is sorted; high load gives a CRIT; low memory plus swap in use gives WARNs; a zombie is flagged; a process with 900 open files is flagged against an assumed limit of 1,000; CPU percent is computed between two samples by injecting a `sleeper` that rewrites `/proc/stat` mid-interval
(it returns 42.105%, matching the hand calculation in Lesson 03); and a `/proc/<pid>` directory without a `status` file is skipped.

## Demo

Running against the "healthy" fixture prints a JSON snapshot (abridged here to the interesting fields) and exits `0`:

```text
"cpus": 4, "cpu_percent": null (no interval for a fixture), "load": [0.74, 0.58, 0.52], "load_per_cpu": 0.185, "runnable": 2,
"mem_available_pct": 75.0, "swap_used_kb": 0, "top_rss": java (2,048,000 kB), systemd (11,000), sshd (7,000), "zombies": [], "max_fds": 120
exit status 0
```

Against the "bad" fixture (low memory, heavy swap use, load 7.0 on 4 CPUs, a zombie and a process with 900 open files):

```text
[CRIT] load per CPU 1.75 > 1.5
[CRIT] only 5.5% memory available
[WARN] swap in use (1597152 kB) while memory is tight
[WARN] zombie processes: [77]
[WARN] a process has 900 open files (limit assumed 1000)
exit status 1
```

## Design discussion

- **Parameterised I/O root.** The only filesystem path used is the `root` argument. The same trick works for `/sys` (device state), cgroup directories (Lesson 06), and `/etc` (Level 2 · Project).
- **Fault tolerance.** `processes()` catches `FileNotFoundError`/`PermissionError`: on a real system a process can exit between `iterdir()` and `read_text()`, and unprivileged users cannot read other users' `fd` directories. A monitor that crashes when a process exits is useless.
- **Deltas and gauges.** CPU needs two samples; memory and load are gauges. The `snapshot` function takes the sampling interval and an injectable sleeper, which keeps tests instant.
- **Thresholds are policy.** `load_per_cpu > 1.5` and `MemAvailable < 10%` are my defaults; a database host or a batch cluster may want others, and thresholds should live in configuration.
- **What it doesn't do:** disk, network, per-core CPU, cgroup-limited containers (it would show host values where `/proc` is host-wide), history or trending, or alert delivery. Real monitoring (Prometheus node_exporter, Level 4) does all of that; the point here is to understand what such tools read.

## Extensions

1. Add disk space and inode checks (`os.statvfs` on mount points read from `/proc/mounts`), with fixtures.
2. Add per-core CPU imbalance detection from `cpuN` lines (one core at 100% while the rest idle).
3. Add cgroup awareness: read `cpu.max`, `cpu.stat` throttling and `memory.events` with Lesson 06's parser, and alert on `oom_kill > 0` or throttled time rising.
4. Output Prometheus text format so a scraper can consume it.
5. Run it on a real Linux host and compare its numbers to `top`, `free` and `uptime`; fix whatever the fixtures got wrong.

## How It Actually Works

Each indicator maps to a kernel counter exposed by procfs (Lesson 03): `stat` accumulates per-state CPU jiffies, `meminfo` reports the memory manager's current accounting (`MemAvailable` is the kernel's own headroom estimate, Lesson 02), `loadavg` the exponentially damped run-queue average (Lesson 04), and `/proc/<pid>/status` and `fd` the per-process state and open files. A monitor is
sampling, differencing and thresholding; because procfs is generated on read, it is cheap to call and always current, but not atomic across files.

## Common mistakes

- **Computing CPU % from one `/proc/stat` reading.**
- **Letting a vanished process crash the scan.**
- **Hard-coding `/proc`** so the tool can't be tested.
- **Alerting on `MemFree`** instead of `MemAvailable`.
- **Thresholds baked into code** and shared across very different hosts.
- **Trusting fixtures as much as the real system.** Run it for real before you rely on it.

## Exercise

1. Run the tests, then break the code deliberately (for example, compute CPU from `total` only) and see which test fails.
2. Add a test fixture and rule for `Dirty` pages exceeding a threshold (Lesson 05).
3. Run `procmon.py /proc` on a Linux VM, then stress it with `stress-ng` or a busy loop and a memory hog, and tune the thresholds.
4. Add a `--json-only` flag and a `--fd-limit` argument, with tests.
