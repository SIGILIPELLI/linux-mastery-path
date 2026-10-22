"""Parse and evaluate 5-field cron expressions (minute hour day-of-month month day-of-week), with Vixie-cron semantics:
if BOTH day-of-month and day-of-week are restricted (not '*'), a day matches if EITHER matches."""
from datetime import datetime, timedelta
NAMES_M = {n: i for i, n in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}
NAMES_D = {n: i for i, n in enumerate("sun mon tue wed thu fri sat".split())}

def _field(spec, lo, hi, names=None):
    out = set()
    for part in spec.lower().split(","):
        step = 1
        if "/" in part: part, s = part.split("/"); step = int(s)
        if part in ("*", ""): a, b = lo, hi
        elif "-" in part:
            x, y = part.split("-"); a, b = (names or {}).get(x, x), (names or {}).get(y, y); a, b = int(a), int(b)
        else:
            a = int((names or {}).get(part, part)); b = hi if step != 1 else a
        if a < lo or b > hi or a > b: raise ValueError(f"value out of range in {spec!r} ({lo}-{hi})")
        out.update(range(a, b + 1, step))
    return out

class Cron:
    def __init__(self, expr):
        f = expr.split()
        if len(f) != 5: raise ValueError("need exactly 5 fields")
        self.dom_star, self.dow_star = f[2].startswith("*"), f[4].startswith("*")
        self.min, self.hour = _field(f[0], 0, 59), _field(f[1], 0, 23)
        self.dom, self.mon = _field(f[2], 1, 31), _field(f[3], 1, 12, NAMES_M)
        d = _field(f[4], 0, 7, NAMES_D); self.dow = {x % 7 for x in d}        # 7 is also Sunday
    def day_ok(self, t):
        dom_ok, dow_ok = t.day in self.dom, (t.isoweekday() % 7) in self.dow
        if not self.dom_star and not self.dow_star: return dom_ok or dow_ok     # the surprising OR rule
        return dom_ok and dow_ok
    def matches(self, t):
        return t.minute in self.min and t.hour in self.hour and t.month in self.mon and self.day_ok(t)
    def next_after(self, t, limit_days=400):
        t = t.replace(second=0, microsecond=0) + timedelta(minutes=1)
        end = t + timedelta(days=limit_days)
        while t < end:
            if self.matches(t): return t
            t += timedelta(minutes=1)
        return None
