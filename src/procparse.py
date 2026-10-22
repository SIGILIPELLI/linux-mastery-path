import re

def parse_meminfo(text):
    out = {}
    for line in text.splitlines():
        m = re.match(r"(\w[\w()]*):\s+(\d+)(?:\s+kB)?", line)
        if m: out[m.group(1)] = int(m.group(2))
    return out

def parse_loadavg(text):
    a, b, c, runq, last = text.split()
    running, total = runq.split("/")
    return {"load1": float(a), "load5": float(b), "load15": float(c), "running": int(running), "total": int(total), "last_pid": int(last)}

def cpu_percent(stat_before, stat_after):
    def vals(s): return list(map(int, s.splitlines()[0].split()[1:]))
    b, a = vals(stat_before), vals(stat_after)
    idle_b, idle_a = b[3] + b[4], a[3] + a[4]                    # idle + iowait
    total_b, total_a = sum(b[:8]), sum(a[:8])                    # user nice system idle iowait irq softirq steal
    return 100.0 * (1 - (idle_a - idle_b) / (total_a - total_b))
