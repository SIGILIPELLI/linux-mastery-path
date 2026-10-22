"""Server hardening linter: checks text configuration files (sshd_config, sysctl, fstab, systemd service units) against a baseline.
Static analysis of text only; it cannot see the running system. Baseline choices are opinions and sources are named in the lesson."""
import sys, pathlib
import fstablint, unitlint

SSHD_DEFAULTS = {  # documented defaults from sshd_config(5)
    "permitrootlogin": "prohibit-password", "passwordauthentication": "yes", "kbdinteractiveauthentication": "yes",
    "pubkeyauthentication": "yes", "permitemptypasswords": "no", "maxauthtries": "6", "logingracetime": "120",
    "x11forwarding": "no", "clientaliveinterval": "0",
}
def sshd_effective(text):
    """First value wins in sshd_config. Match blocks are not modelled: stop at the first 'Match' line."""
    cfg = dict(SSHD_DEFAULTS); seen = set()
    for line in text.splitlines():
        s = line.split("#", 1)[0].strip()
        if not s: continue
        if s.lower().startswith("match "): break
        k, _, v = s.partition(" "); k = k.lower(); v = v.strip()
        if k not in seen: cfg[k] = v.lower() if k != "allowusers" and k != "allowgroups" else v; seen.add(k)
        if k in ("allowusers", "allowgroups"): cfg[k] = v
    return cfg

def check_sshd(text):
    c = sshd_effective(text); out = []
    if c["permitrootlogin"] != "no": out.append(("HIGH", f"sshd: PermitRootLogin is {c['permitrootlogin']!r}; set 'no'"))
    if c["passwordauthentication"] != "no": out.append(("HIGH", "sshd: PasswordAuthentication is enabled; use keys and set 'no'"))
    if c["kbdinteractiveauthentication"] != "no": out.append(("MEDIUM", "sshd: KbdInteractiveAuthentication enabled (a second password path unless PAM-MFA is intended)"))
    if c["permitemptypasswords"] != "no": out.append(("HIGH", "sshd: PermitEmptyPasswords must be 'no'"))
    if c["pubkeyauthentication"] != "yes": out.append(("HIGH", "sshd: PubkeyAuthentication disabled"))
    if int(c["maxauthtries"]) > 4: out.append(("LOW", f"sshd: MaxAuthTries {c['maxauthtries']}; consider 3"))
    if int(c["logingracetime"]) > 60: out.append(("LOW", f"sshd: LoginGraceTime {c['logingracetime']}s; consider 30"))
    if c["x11forwarding"] != "no": out.append(("LOW", "sshd: X11Forwarding enabled"))
    if "allowusers" not in c and "allowgroups" not in c: out.append(("MEDIUM", "sshd: no AllowUsers/AllowGroups; every account may attempt login"))
    return out

SYSCTL_BASELINE = {  # key -> required value, with reason
    "net.ipv4.conf.all.rp_filter": ("1", "reverse-path filtering drops spoofed sources"),
    "net.ipv4.tcp_syncookies": ("1", "SYN flood mitigation"),
    "net.ipv4.conf.all.accept_redirects": ("0", "ignore ICMP redirects"),
    "net.ipv4.conf.all.send_redirects": ("0", "do not send ICMP redirects unless routing"),
    "net.ipv4.ip_forward": ("0", "disable forwarding unless this host is a router/container host"),
    "kernel.randomize_va_space": ("2", "full ASLR"),
    "fs.protected_symlinks": ("1", "restrict symlink following in sticky dirs"),
    "kernel.kptr_restrict": ("1", "hide kernel pointers from unprivileged users"),
}
def check_sysctl(text):
    got = {}
    for line in text.splitlines():
        s = line.split("#", 1)[0].split(";", 1)[0].strip()
        if "=" in s: k, v = s.split("=", 1); got[k.strip()] = v.strip()
    out = []
    for k, (want, why) in SYSCTL_BASELINE.items():
        if k not in got: out.append(("LOW", f"sysctl: {k} not set (want {want}: {why})"))
        elif got[k] != want: out.append(("MEDIUM", f"sysctl: {k}={got[k]} (want {want}: {why})"))
    return out

def run(sshd="", sysctl="", fstab="", units=()):
    findings = check_sshd(sshd) + check_sysctl(sysctl)
    findings += [("MEDIUM", "fstab: " + p) for p in fstablint.lint(fstab)]
    for name, text in units: findings += [("MEDIUM", f"unit {name}: " + p) for p in unitlint.lint(text)]
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    return sorted(findings, key=lambda f: order[f[0]])

if __name__ == "__main__":
    d = pathlib.Path(sys.argv[1])
    rd = lambda n: (d / n).read_text() if (d / n).exists() else ""
    f = run(rd("sshd_config"), rd("sysctl.conf"), rd("fstab"), [(p.name, p.read_text()) for p in d.glob("*.service")])
    for sev, msg in f: print(f"[{sev}] {msg}")
    h = sum(1 for s, _ in f if s == "HIGH")
    print(f"{len(f)} finding(s), {h} high"); sys.exit(1 if h else 0)
