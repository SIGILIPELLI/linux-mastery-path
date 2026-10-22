"""Helpers for reading cgroup v2 interface files (formats from the kernel's cgroup-v2 documentation). Run against fixtures here."""
def cpu_limit(cpu_max_text):
    """cpu.max is '$MAX $PERIOD' in microseconds; 'max' means unlimited. Returns the CPU count the group may consume."""
    quota, period = cpu_max_text.split()
    return None if quota == "max" else int(quota) / int(period)

def parse_flat_keyed(text):
    """Flat-keyed files such as memory.events: 'key value' per line."""
    return {k: int(v) for k, v in (line.split() for line in text.strip().splitlines())}

def proc_cgroup_path(text):
    """/proc/<pid>/cgroup in v2 has a single line '0::/path'."""
    for line in text.strip().splitlines():
        hid, controllers, path = line.split(":", 2)
        if hid == "0" and controllers == "": return path
    return None

def was_oom_killed(events_text):
    e = parse_flat_keyed(events_text); return e.get("oom_kill", 0) > 0
