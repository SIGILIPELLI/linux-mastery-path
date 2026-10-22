"""File integrity monitoring in miniature (the idea behind AIDE/Tripwire): record a baseline of file hashes and metadata, later compare."""
import hashlib, json, os, stat, sys
from pathlib import Path

def sha256(path, bufsize=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(bufsize), b""): h.update(chunk)
    return h.hexdigest()

def scan(root, exclude=()):
    out = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in exclude)
        for name in sorted(filenames):
            p = Path(dirpath) / name; rel = str(p.relative_to(root))
            st = p.lstat()
            if stat.S_ISLNK(st.st_mode): out[rel] = {"type": "symlink", "target": os.readlink(p), "mode": stat.S_IMODE(st.st_mode)}
            elif stat.S_ISREG(st.st_mode):
                out[rel] = {"type": "file", "sha256": sha256(p), "mode": stat.S_IMODE(st.st_mode), "uid": st.st_uid, "size": st.st_size}
    return out

def compare(baseline, current):
    findings = []
    for path in sorted(set(baseline) | set(current)):
        b, c = baseline.get(path), current.get(path)
        if b is None: findings.append(("ADDED", path, "")); continue
        if c is None: findings.append(("REMOVED", path, "")); continue
        if b.get("sha256") != c.get("sha256"): findings.append(("MODIFIED", path, "content hash changed"))
        if b.get("target") != c.get("target"): findings.append(("MODIFIED", path, f"symlink target {b.get('target')} -> {c.get('target')}"))
        if b["mode"] != c["mode"]: findings.append(("PERMS", path, f"{b['mode']:04o} -> {c['mode']:04o}"))
        if b.get("uid") != c.get("uid"): findings.append(("OWNER", path, f"uid {b.get('uid')} -> {c.get('uid')}"))
    return findings

if __name__ == "__main__":
    cmd, root, db = sys.argv[1], sys.argv[2], sys.argv[3]
    if cmd == "init": Path(db).write_text(json.dumps(scan(root), indent=1, sort_keys=True)); print(f"baseline of {len(json.loads(Path(db).read_text()))} entries written")
    elif cmd == "check":
        f = compare(json.loads(Path(db).read_text()), scan(root))
        for kind, path, detail in f: print(f"{kind:<9} {path} {detail}".rstrip())
        print(f"{len(f)} change(s)"); sys.exit(1 if f else 0)
