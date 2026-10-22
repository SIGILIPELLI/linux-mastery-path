"""Triage a Linux `vmstat` sample using the USE method (Utilization, Saturation, Errors). Fixture-driven; thresholds are rules of thumb."""
COLS = "r b swpd free buff cache si so bi bo in cs us sy id wa st".split()

def parse(text):
    rows = []
    for line in text.strip().splitlines():
        f = line.split()
        if not f or not f[0].isdigit(): continue                      # skip the two header lines
        if len(f) != len(COLS): raise ValueError(f"expected {len(COLS)} columns, got {len(f)}")
        rows.append(dict(zip(COLS, map(int, f))))
    return rows

def triage(rows, ncpu):
    steady = rows[1:] if len(rows) > 1 else rows                     # the first vmstat line is an average since boot
    avg = lambda k: sum(r[k] for r in steady) / len(steady)
    out = []
    if avg("r") > ncpu: out.append(f"CPU saturation: run queue {avg('r'):.1f} > {ncpu} CPUs")
    if avg("us") + avg("sy") > 85: out.append(f"CPU utilization {avg('us') + avg('sy'):.0f}% (us+sy)")
    if avg("wa") > 20: out.append(f"I/O wait {avg('wa'):.0f}%: tasks blocked on storage")
    if avg("st") > 5: out.append(f"CPU steal {avg('st'):.0f}%: the hypervisor is taking CPU")
    if avg("si") + avg("so") > 0: out.append(f"swapping: si={avg('si'):.0f} so={avg('so'):.0f} KB/s: memory pressure")
    if avg("b") > 0: out.append(f"{avg('b'):.1f} tasks blocked in uninterruptible sleep on average")
    if avg("cs") > 50000: out.append(f"{avg('cs'):.0f} context switches/s: check lock contention / thread count")
    return out or ["no obvious saturation in this sample"]
