"""Lint /etc/fstab text for common boot-time hazards. Static checks only."""
import re, sys

def parse(text):
    rows = []
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"): continue
        f = s.split()
        rows.append((n, f))
    return rows

def lint(text):
    problems = []
    for n, f in parse(text):
        if len(f) < 4: problems.append(f"line {n}: needs at least 4 fields (device mountpoint type options), got {len(f)}"); continue
        dev, mp, fstype, opts = f[:4]
        dump = f[4] if len(f) > 4 else "0"
        passno = f[5] if len(f) > 5 else "0"
        o = set(opts.split(","))
        if re.match(r"^/dev/(sd|vd|nvme|xvd)", dev): problems.append(f"line {n}: {dev} is an unstable device name; use UUID= or LABEL= (names can change between boots)")
        if fstype in ("nfs", "nfs4", "cifs", "smb3") and not ({"nofail", "_netdev"} & o): problems.append(f"line {n}: network mount {mp} without _netdev/nofail can block or fail boot")
        if mp not in ("/", "swap", "none", "/boot", "/boot/efi", "/usr", "/var") and "nofail" not in o and fstype not in ("proc", "sysfs", "tmpfs", "devpts") and not dev.startswith(("proc", "sys", "tmpfs", "devpts")):
            problems.append(f"line {n}: {mp} is not marked nofail; if the disk is missing boot drops to emergency mode (fine for essential mounts, risky for data disks)")
        if mp == "/" and passno != "1": problems.append(f"line {n}: root filesystem should have fsck pass 1, got {passno}")
        if fstype == "xfs" and passno != "0": problems.append(f"line {n}: xfs does not use fsck at boot; pass should be 0")
        if mp in ("/tmp", "/var/tmp", "/dev/shm") and not {"noexec", "nosuid"} <= o: problems.append(f"line {n}: {mp} without noexec,nosuid (hardening)")
        if fstype == "swap" and mp != "none" and mp != "swap": problems.append(f"line {n}: swap entries conventionally use 'none' as the mount point")
        if not re.match(r"^[0-2]$", dump) or not re.match(r"^[0-2]$", passno): problems.append(f"line {n}: dump/pass fields must be 0, 1 or 2")
    mounts = [f[1] for _, f in parse(text) if len(f) >= 2]
    for m in set(mounts):
        if m not in ("none", "swap") and mounts.count(m) > 1: problems.append(f"mount point {m} appears {mounts.count(m)} times")
    return problems

if __name__ == "__main__":
    p = lint(open(sys.argv[1]).read()); print("\n".join(p) if p else "OK"); sys.exit(1 if p else 0)
