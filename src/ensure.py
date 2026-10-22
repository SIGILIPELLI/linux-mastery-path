"""A miniature configuration-management library: declarative 'ensure' operations that are idempotent and report whether they changed anything.
Each function returns 'changed' or 'ok'. Supports check mode (dry run). Not a replacement for Ansible/Puppet; it shows the core idea."""
import os, stat, tempfile
from pathlib import Path

class Run:
    def __init__(self, check=False): self.check, self.log = check, []
    def record(self, what, status): self.log.append((what, status)); return status
    def summary(self):
        changed = sum(1 for _, s in self.log if s == "changed"); return f"{len(self.log)} tasks, {changed} changed, {len(self.log) - changed} ok"

def ensure_dir(run, path, mode=0o755):
    p = Path(path); status = "ok"
    if not p.is_dir(): status = "changed"; None if run.check else p.mkdir(parents=True)
    if p.is_dir() and stat.S_IMODE(p.stat().st_mode) != mode:
        status = "changed"; None if run.check else os.chmod(p, mode)
    return run.record(f"dir {path}", status)

def ensure_line(run, path, line):
    p = Path(path); lines = p.read_text().splitlines() if p.exists() else []
    if line in lines: return run.record(f"line in {path}", "ok")
    if not run.check: p.write_text("\n".join(lines + [line]) + "\n")
    return run.record(f"line in {path}", "changed")

def ensure_file(run, path, content, mode=0o644):
    """Replace a file atomically only when content or mode differ."""
    p = Path(path); same = p.exists() and p.read_text() == content and stat.S_IMODE(p.stat().st_mode) == mode
    if same: return run.record(f"file {path}", "ok")
    if not run.check:
        fd, tmp = tempfile.mkstemp(dir=p.parent); os.write(fd, content.encode()); os.close(fd); os.chmod(tmp, mode); os.replace(tmp, p)
    return run.record(f"file {path}", "changed")

def ensure_symlink(run, link, target):
    l = Path(link)
    if l.is_symlink() and os.readlink(l) == str(target): return run.record(f"symlink {link}", "ok")
    if not run.check:
        if l.is_symlink() or l.exists(): l.unlink()
        l.symlink_to(target)
    return run.record(f"symlink {link}", "changed")

def converge(run, root):
    ensure_dir(run, f"{root}/etc/myapp"); ensure_dir(run, f"{root}/var/lib/myapp", 0o750)
    ensure_file(run, f"{root}/etc/myapp/app.conf", "port=8080\nworkers=4\n", 0o640)
    ensure_line(run, f"{root}/etc/hosts", "10.0.0.5 db.internal")
    ensure_symlink(run, f"{root}/etc/myapp/current", f"{root}/var/lib/myapp")
    return run
