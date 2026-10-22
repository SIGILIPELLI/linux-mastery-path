---
description: "Level 2 project: a hardening linter for sshd_config, sysctl, fstab and systemd units, with severities, 8 tests and a demo run."
---

# 10 · Project — A Server Hardening Linter

You have now met SSH hardening (Lesson 08), systemd units (02), fstab (04), and firewall design (07). This project joins them into one tool: it reads the **text configuration** of a server, applies a baseline, and reports findings by severity. Because it only reads files, you can
develop and test it on any machine, then point it at a copy of a real server's `/etc`.

!!! note "What was run, and the limits of the tool"
    The linter and its **8 pytest tests were run on macOS** (Python 3.12). The inputs in the demo are **hand-written fixtures**, not taken from a real server. The baseline is **my selection** of widely published hardening guidance (OpenSSH documented defaults from `sshd_config(5)`, common
    sysctl recommendations), not the output of an official benchmark such as CIS, and I have not verified each sysctl value against a particular distribution's defaults. It cannot see the running system (loaded kernel parameters, actual listening ports, patch level) and it does not model sshd `Match`
    blocks. Treat it as a pre-commit/CI check on configuration text. See Level 1 · Lesson 01.

## Design

```text
files → parsers → checks → findings (severity, message) → sorted report → exit code (1 if any HIGH)
sshd_config   → effective values (documented defaults + first value wins; stop at Match)
sysctl.conf   → key=value map vs baseline
fstab         → fstablint.py (Lesson 04)
*.service     → unitlint.py  (Lesson 02)
```

Reuse is the point: the fstab and unit linters from earlier lessons are imported unchanged. Severity is a judgment call, so it's data in the checks, not scattered through the code.

## harden.py

```python
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
```

Notes on the design:

- **Defaults matter.** `sshd_effective` starts from the documented defaults (so an *empty* config is evaluated as "defaults", not "fine") and applies the first occurrence of each keyword, which is sshd's rule. The test `test_defaults_alone_are_not_enough` proves an empty file still fails: `PasswordAuthentication` defaults to
  `yes`, and `PermitRootLogin` defaults to `prohibit-password`, which the baseline wants as an explicit `no`.
- **`Match` blocks** can override settings per user or address; the parser stops at the first `Match` line, which is a documented limitation rather than a correct implementation. A test pins that behaviour (`PasswordAuthentication no` before a `Match User legacy` block that re-enables it is reported as `no`), so a future improvement is a conscious change.
- Findings are sorted HIGH first, and the exit status is `1` only for HIGH, so CI can block on serious issues while only printing lower ones.

## Tests

```python
import harden
from harden import check_sshd, check_sysctl, sshd_effective

def sev(findings, needle): return [s for s, m in findings if needle in m]

def test_defaults_alone_are_not_enough():
    f = check_sshd("")                               # empty config = documented defaults
    assert "HIGH" in sev(f, "PasswordAuthentication")
    assert sev(f, "PermitRootLogin") == ["HIGH"]     # the default is prohibit-password; the baseline wants an explicit 'no'

def test_hardened_sshd_clean():
    cfg = "PermitRootLogin no\nPasswordAuthentication no\nKbdInteractiveAuthentication no\nAllowGroups ssh-users\nMaxAuthTries 3\nLoginGraceTime 30\n"
    assert check_sshd(cfg) == []

def test_first_value_wins():
    assert sshd_effective("PermitRootLogin no\nPermitRootLogin yes\n")["permitrootlogin"] == "no"

def test_match_block_not_applied_globally():
    cfg = "PasswordAuthentication no\nMatch User legacy\n    PasswordAuthentication yes\n"
    assert sshd_effective(cfg)["passwordauthentication"] == "no"

def test_comments_and_case():
    assert sshd_effective("permitrootlogin NO # allow nothing\n")["permitrootlogin"] == "no"

def test_sysctl_missing_and_wrong():
    f = check_sysctl("net.ipv4.tcp_syncookies = 0\nkernel.randomize_va_space=2\n")
    assert sev(f, "tcp_syncookies") == ["MEDIUM"] and not sev(f, "randomize_va_space") and sev(f, "rp_filter") == ["LOW"]

def test_run_sorts_high_first():
    f = harden.run(sshd="PasswordAuthentication yes\n", sysctl="")
    assert f[0][0] == "HIGH" and f[-1][0] == "LOW"

def test_integrates_fstab_and_unit_linters():
    f = harden.run(fstab="/dev/sdb1 /srv ext4 defaults 0 2\n", units=[("bad.service", "[Service]\nExecStart=app\n")])
    assert any("fstab:" in m for _, m in f) and any("unit bad.service:" in m for _, m in f)
```

```text
8 passed in 0.01s
```

One test was wrong the first time: I had written two contradictory assertions about the same finding (`PermitRootLogin` both "not HIGH" and "HIGH"), and the suite failed until I fixed the test. When a test fails, decide whether the code or the *test* encodes a mistake.

## Demo run

A fixture directory with a weak `sshd_config` (`PermitRootLogin yes`, `PasswordAuthentication yes`, `X11Forwarding yes`), a `sysctl.conf` enabling IP forwarding, a two-line `fstab` using `/dev/sdb1`, and a minimal service unit. Running `python harden.py demo`:

```text
[HIGH] sshd: PermitRootLogin is 'yes'; set 'no'
[HIGH] sshd: PasswordAuthentication is enabled; use keys and set 'no'
[MEDIUM] sshd: KbdInteractiveAuthentication enabled (a second password path unless PAM-MFA is intended)
[MEDIUM] sshd: no AllowUsers/AllowGroups; every account may attempt login
[MEDIUM] sysctl: net.ipv4.ip_forward=1 (want 0: disable forwarding unless this host is a router/container host)
[MEDIUM] fstab: line 2: /dev/sdb1 is an unstable device name; use UUID= or LABEL= (names can change between boots)
[MEDIUM] fstab: line 2: /srv is not marked nofail; if the disk is missing boot drops to emergency mode (fine for essential mounts, risky for data disks)
[MEDIUM] unit api.service: no Restart= policy (default is no restart)
[MEDIUM] unit api.service: little sandboxing: consider NoNewPrivileges=, ProtectSystem=, PrivateTmp=, ProtectHome=
[LOW] sshd: MaxAuthTries 6; consider 3
[LOW] sshd: LoginGraceTime 120s; consider 30
[LOW] sshd: X11Forwarding enabled
[LOW] sysctl: net.ipv4.conf.all.rp_filter not set (want 1: reverse-path filtering drops spoofed sources)
[LOW] sysctl: net.ipv4.conf.all.accept_redirects not set (want 0: ignore ICMP redirects)
[LOW] sysctl: net.ipv4.conf.all.send_redirects not set (want 0: do not send ICMP redirects unless routing)
[LOW] sysctl: fs.protected_symlinks not set (want 1: restrict symlink following in sticky dirs)
[LOW] sysctl: kernel.kptr_restrict not set (want 1: hide kernel pointers from unprivileged users)
17 finding(s), 2 high
```

The exit status was `1`. Triage the output the way you would a real audit: the two HIGH sshd findings first; then ask of each MEDIUM whether it is a real exposure *for this server's role* (`ip_forward=1` is correct on a router or a container host, wrong on a plain web server: the linter can't know the role, so
a real tool needs a role/profile). A finding is a question, not a verdict.

## Extensions

1. Add a profile mechanism (`web`, `router`, `bastion`) that changes the baseline, with tests per profile.
2. Parse `/etc/ssh/sshd_config.d/*.conf` in the order sshd reads them (included files come first in many distributions, and first value wins).
3. Add checks for `login.defs` password aging, `sudoers` `NOPASSWD: ALL`, and world-readable private keys under `/etc/ssl/private` (needs a directory listing fixture).
4. Output SARIF or JSON and add it to the CI pipeline from Level 4 · 03.

## How It Actually Works

Each checker is a pure function from text to a list of (severity, message), which makes the tool trivially testable: no files, no network, no root. That is the same pattern as the PySpark transform tests in the Databricks course and the unit-file linter here: parse, normalise (apply defaults and precedence), compare to a baseline. The part that needs
care is *normalisation*: most real-world configuration bugs are about what the program ends up using (defaults, ordering, includes, overrides), not what a line says. Where possible ask the program itself (`sshd -T`, `systemd-analyze verify`, `sysctl -a`) and use text linting only when the program isn't available.

## Common mistakes

- **Linting only what is written** and ignoring documented defaults.
- **One baseline for every role of server.**
- **Treating a clean report as security.**
- **Hard-coding severity in many places** instead of data.
- **No tests for the negative cases** (hardened config must be clean).
- **Applying the "fix" list blindly** to production: some findings, like `ip_forward`, are correct for some hosts.

## Exercise

1. Run the tests, then change the `MaxAuthTries` threshold and update the test to match; explain why the threshold is a policy decision.
2. Add `ClientAliveInterval`/`ClientAliveCountMax` checks and a test for the default (`0`, meaning disabled, per the man page).
3. Write a fixture for a hardened server (sshd, sysctl, fstab, unit) that produces **zero** findings, and add it as a regression test.
4. Run it on a real Linux server's copied configuration, triage every finding, and record which you chose not to fix and why.
