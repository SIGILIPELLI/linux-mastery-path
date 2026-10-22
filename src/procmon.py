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
