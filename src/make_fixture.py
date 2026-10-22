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
