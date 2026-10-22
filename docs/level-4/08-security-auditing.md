---
description: "Security auditing on Linux: auditd rules, auth-log review, Lynis-style audits, and file integrity monitoring built and tested as a mini AIDE."
---

# 08 · Security Auditing: auditd, Lynis & Logs

Hardening (Level 2 · 10) reduces the attack surface; **auditing** tells you whether it's still reduced and whether anyone is attacking or misusing the system. Three questions: *What is the configuration now (and does it match policy)? What happened (who did what)? Did anything change that shouldn't have?* This lesson covers the Linux tools for each and builds the third
as code.

!!! note "What was run"
    `auditd`, `Lynis`, `ausearch`, `lastb` and SELinux/AppArmor tooling are Linux software and **were not run**. The audit-rule syntax comes from `audit.rules(7)` (man7.org, October 2026). The **file-integrity monitor below, with 7 passing pytest tests and a demo, ran on macOS** against temporary directories. The authentication-log analysis uses the hand-written fixture from Level 2 · Lesson 03. See Level 1 · Lesson 01.

## 1. Auditing configuration: Lynis and compliance scanners

Tools such as **Lynis** (open source), OpenSCAP (SCAP content like the CIS and DISA STIG benchmarks), and vendor scanners inspect a host and report deviations: SSH settings, password policy, file permissions, kernel parameters, installed packages with known vulnerabilities. Typical use: `sudo lynis audit system` produces a report with warnings, suggestions and a hardening index. (I did not run it here.) Treat the output as a *to-do
list for judgement*, not a score to maximise, since some suggestions don't fit your workload, as the `ip_forward` example in Level 2 showed. Automate the checks that matter to you (like the linter in Level 2 · 10) and run them from CI or config management (Lesson 03). A vulnerability scanner tied to your package inventory (Lesson 05) answers "are we patched?".

## 2. Recording what happens: the Linux audit system

The kernel audit subsystem and the `auditd` daemon record security-relevant events: file access, system calls, logins, privilege changes, SELinux denials. Logs go to `/var/log/audit/audit.log`. Rules go in `/etc/audit/rules.d/*.rules` and are loaded with `augenrules --load`.

Per `audit.rules(7)`, watch rules for a path take this form:

```text
-a always,exit -F arch=b64 -F path=path-to-file -F perm=permissions -F key=keyname
```

where permissions are any of `r` (read), `w` (write), `x` (execute), `a` (attribute change), and **syscall rules** take the form `-a action,list -S syscall -F field=value -k keyname`, with `always` creating an event. A concise watch shorthand (`-w path -p wa -k key`) exists too. Examples of what to watch (illustrative, not run):

```text
-w /etc/passwd -p wa -k identity
-w /etc/shadow -p wa -k identity
-w /etc/sudoers -p wa -k privilege
-w /etc/ssh/sshd_config -p wa -k sshd
-a always,exit -F arch=b64 -S execve -F euid=0 -F auid>=1000 -F auid!=-1 -k root-commands
-a always,exit -F arch=b64 -S mount -S umount2 -k mounts
```

The `auid` field is the **audit user ID**: set at login and inherited, so it still identifies the original user after `sudo` or `su`, which is the audit system's most valuable property: "root did it" becomes "alice, via sudo, did it". Query with `ausearch -k identity -ts today -i` and summarise with `aureport --auth --summary`. Always add a `-k key` so events can be found; avoid rules that generate enormous volume (watching every `read` or `open` on a busy system) because
audit can slow the machine and fill the disk (set `max_log_file` and disk-full actions deliberately); and consider immutability (`-e 2` as the last rule locks the rules until reboot, so an intruder can't switch auditing off, at the cost of needing a reboot to change rules).

Ship audit logs off the host (Level 2 · 03): an attacker with root can edit local logs.

## 3. Reading authentication logs

On Debian-family systems `/var/log/auth.log`, on RHEL-family `/var/log/secure`, and the journal (`journalctl -u ssh`) record logins, `sudo` and `su`. Useful commands:

```bash
last -n 20 ; lastb | head          # successful logins; failed logins (needs root)
journalctl -u ssh --since yesterday | grep -E "Failed|Accepted|Invalid user"
grep "sudo:" /var/log/auth.log | grep -i COMMAND
```

With the fixture from Level 2 · Lesson 03, the earlier pipeline `awk '/Failed password/ {for(i=1;i<=NF;i++) if($i=="from") print $(i+1)}' | sort | uniq -c` counted 2 failures from 203.0.113.5. On a real server exposed to the internet you will see thousands of such lines daily; the signals worth acting on are: **a success after many failures from the same source** (brute force worked), logins for accounts that shouldn't log in, logins at odd hours or from unusual
countries, new entries in `authorized_keys`, `sudo` use by accounts that normally don't, and sudden changes in the count of failures. Fail2ban or `sshd` rate limits reduce noise; key-only SSH and source allowlists (Level 2 · 07, 08) remove the risk.

## 4. Detecting change: file integrity monitoring (run)

File integrity monitoring (FIM), as implemented by AIDE and Tripwire, stores a **baseline** of hashes and metadata for important files and later reports differences. A compromised `sshd_config`, an added backdoor script, a replaced binary, a changed permission: all show up. My miniature version:

```python
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
```

Its tests (7 passing) build a small `etc` tree and check: no changes yields no findings; a modified file is reported as `MODIFIED ... content hash changed`; added and removed files; a permission change `0644 -> 0666`; a retargeted symlink; exclusions; and an important one: **a same-length content change with the original modification time restored is still detected**, because the tool compares hashes, not size and mtime (compare Lesson 02's rsync trap, where size+mtime missed exactly this).

Demo (macOS temp directory):

```text
$ fim.py init etc base.json   →  baseline of 3 entries written
$ fim.py check etc base.json  →  0 change(s)                                      (exit 0)
  ... then: sshd_config changed to "PermitRootLogin yes", passwd chmod 666, a new evil.sh added ...
$ fim.py check etc base.json  →  ADDED     evil.sh
                                 PERMS     passwd 0644 -> 0666
                                 MODIFIED  ssh/sshd_config content hash changed
                                 3 change(s)                                       (exit 1)
```

Real FIM must also handle: **legitimate changes** (package updates change binaries: re-baseline after patching, ideally by comparing against the package manager's own hashes with `debsums` or `rpm -V`), **the baseline's own integrity** (store it off-host or read-only, and sign it, since an attacker who can edit files can edit the baseline), **noise** (exclude logs and caches), and **performance** (hash only important paths; `/etc`, `/usr/bin`, `/usr/sbin`, `/boot`, `~/.ssh`). Note that FIM runs *after the fact*: it detects tampering but doesn't prevent it.

## 5. Privilege and access review

A periodic review answers: who has an account, and should they? Who can `sudo`? Which accounts have keys in `authorized_keys`? Which files are setuid (Level 1 · 04 and the audit script in the Level 1 project)? Which services listen on the network (`ss -ltnup`)? Which cron jobs and timers exist and run as whom? Which packages and containers are outdated? Automate the inventory, review diffs rather than full lists, and record
sign-off. Remove accounts and keys promptly when people leave (a leading source of long-lived access).

## How It Actually Works

The audit subsystem hooks into the kernel at system-call entry/exit and certain security hooks (Level 3 · 07), evaluates the loaded rule list for each event, and queues matching events to a netlink socket read by `auditd`, which writes them with fields like `type=SYSCALL ... auid=1000 uid=0 comm="vim" exe="/usr/bin/vim" key="identity"`. The login UID (`auid`) is stored in the process's credentials at login by PAM and cannot be changed by the process afterward, which
is why it survives privilege changes. FIM tools just read files and hash them in user space, so they cost I/O proportional to the monitored data. Neither mechanism prevents an attack: they produce evidence, and their value depends on someone (or something) reading it and on the evidence being stored where an attacker can't rewrite it.

## Common mistakes

- **Collecting audit logs nobody reads**, or alerting on everything.
- **Audit rules so broad they drown the system**, or no `-k` keys.
- **Keeping logs only on the host** being attacked.
- **FIM with a baseline stored on the same host, writable**, or never re-baselined, so everything alerts.
- **Treating a Lynis/benchmark score** as the goal.
- **Not reviewing accounts, keys, sudoers and listeners periodically.**
- **Disabling SELinux/AppArmor** (Level 3 · 07) and losing their denial logs.
- **Clock drift** across hosts ruining log correlation (run NTP/chrony).

## Exercise

1. Write `auditd` rules to record changes to `/etc/passwd`, `/etc/shadow`, `/etc/sudoers` and `/etc/ssh/sshd_config` and every `execve` by root with a real user's `auid`; trigger each on a test VM and find the events with `ausearch`.
2. Extend the FIM with a `--update` mode that re-baselines selected paths, a signed baseline (HMAC with a key kept elsewhere), and a test that a tampered baseline is rejected.
3. Write a script that scans the auth log for "success after N failures from the same IP" and test it on a fixture.
4. Compare `debsums -c` or `rpm -Va` output with your FIM on a test system after installing a package update; explain the differences.
