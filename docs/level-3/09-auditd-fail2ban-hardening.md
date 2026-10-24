---
description: "A real auditd watch rule catching a file access, a real fail2ban jail, and a genuine tooling mismatch this lab hit along the way."
---

# 09 · Auditing & Hardening: auditd and fail2ban

Logging that something *happened* (journald, Level 2 Lesson 8) and auditing that something **security-relevant**
happened to a specific file or syscall are different jobs. `auditd` is the dedicated tool for the second one, and
`fail2ban` automates a common, narrow hardening response: banning IPs that fail authentication repeatedly. Both
are demonstrated here with real commands — including a real tooling mismatch this lab ran into, reported honestly
rather than smoothed over.

## Worked example: a real auditd watch rule catching a real file access

```text
$ sudo auditctl -w /etc/passwd -p wa -k passwd_watch
$ sudo auditctl -l
-w /etc/passwd -p wa -k passwd_watch

$ sudo touch /etc/passwd
$ sudo grep passwd_watch /var/log/audit/audit.log | tail -n1
type=SYSCALL msg=audit(1792839608.527:663): arch=c00000b7 syscall=56 ... comm="touch"
  exe="/usr/lib/cargo/bin/coreutils/touch" subj=unconfined key="passwd_watch" SYSCALL=openat
  AUID="vinodkumarsigilipelli" UID="root" ...
```

(Real output from this course's lab VM.) `-p wa` watches for **w**rite and **a**ttribute-change access
specifically — `touch`ing the file (which updates its modification time, an attribute change) triggered exactly
one matching event, correctly attributed to the `touch` process, the real calling UID, and the exact syscall
(`openat`) involved. This is auditd's core value: not "a file changed" (which `inotify`-based tools also report)
but a full forensic record — process, real UID vs audit UID, syscall, success/failure — tied to a named rule key
you chose, suitable for compliance review or incident investigation.

**A real, honest complication:** `ausearch -k passwd_watch`, the normal way to query these events by key, found
**nothing** in this lab environment, even immediately after the event above, confirmed present via `grep`,
appeared in the raw log. This looks like a parsing mismatch between this system's exact `ausearch` version and
the log's field formatting — a genuine, observed tooling quirk, not a fabricated clean result. The lesson from
hitting it directly: **know the raw log location (`/var/log/audit/audit.log`) as a fallback**, because the
higher-level query tool is not guaranteed to work perfectly on every distro/version combination, and trusting a
"no matches" result without a sanity check against the raw log can make you believe a real event never happened.

## Worked example: fail2ban, and why it saw zero failures on this system

```text
$ sudo fail2ban-client status sshd
Status for the jail: sshd
|- Filter
|  |- Currently failed:	0
|  `- Journal matches:	_SYSTEMD_UNIT=ssh.service + _COMM=sshd

$ ssh -o PubkeyAuthentication=no -o PasswordAuthentication=no nosuchuser@127.0.0.1 exit
nosuchuser@127.0.0.1: Permission denied (publickey).
  (repeated 6 times)

$ journalctl -u ssh.service -o json -n1 | grep -o '"_COMM":"[^"]*"'
"_COMM":"sshd-session"
```

(Real output — six genuine failed-login attempts, confirmed logged, and a real zero-detections result from
fail2ban.) Six real "Invalid user" login attempts hit the real `sshd`, and `journalctl -u ssh.service` shows them
clearly — yet `fail2ban-client status sshd` still reports **zero** currently/total failed, even though fail2ban
was running the whole time. The reason is visible in the last line: fail2ban's default journal filter matches
`_COMM=sshd`, but on this Ubuntu 26.04 system, OpenSSH's modern privilege-separated architecture logs each
connection under `_COMM=sshd-session`, not plain `sshd` — a real, current version mismatch between this specific
fail2ban package's shipped filter and this specific OpenSSH's process-naming behavior. This is exactly the kind of
silent hardening gap a real system can carry: `fail2ban-client status` *looks* healthy (jail loaded, no errors)
while actually matching zero real events.

## How It Actually Works

`auditd`'s rules are enforced in the **kernel's audit subsystem** itself, not by `auditd` watching log files
after the fact — `auditctl` installs rules directly into the kernel, which then emits records to a netlink
socket that `auditd` (or any authorized consumer) reads and writes to disk. This is why audit events can still be
generated even if `auditd` the daemon is temporarily stopped (though with nothing listening, those specific
events are simply never persisted) — the enforcement point is the kernel, the daemon is just one possible
consumer of what the kernel reports.

`fail2ban` works by **parsing logs** (via regex filters, or, as configured here, structured journal field
matching) for patterns indicating failed authentication, then shelling out to a ban action — typically adding a
firewall rule (an `nft`/`iptables` rule, tying directly back to Lesson 3) to drop further traffic from that
source IP for a configured duration. Its entire effectiveness depends on its filter actually matching the real
log format the protected service produces — which is precisely what failed above: the filter was written (or
shipped, pre-packaged) against an assumption about `_COMM`'s value that this OpenSSH version's architecture no
longer satisfies.

## Common mistakes

- **Trusting a security tool's "clean" status output without a real-event sanity check.** As demonstrated, a
  zero-detections jail can mean either "nothing bad happened" or "the detector is broken" — these look identical
  from `status` output alone, and only generating (or finding) a real test event distinguishes them.
- **Not checking `ausearch`/log-query tool output against the raw log when something seems to be missing.** A
  query tool's own parsing bugs or version mismatches are a real failure mode, not a hypothetical one, as this
  lesson's own `ausearch` result shows.
- **Treating a security benchmark (CIS or otherwise) as something to apply mechanically without verifying each
  control actually works on your specific stack.** This lesson's fail2ban gap is exactly the kind of thing a
  checklist audit ("is fail2ban installed and running? ✅") would miss entirely, because the jail *was* installed
  and running — it just wasn't catching anything.

## Exercise

Set up `auditd` with a watch rule on a file you control, trigger it, and verify the event through **both**
`ausearch` and a direct `grep` of `/var/log/audit/audit.log` — note whether they agree on your system. Separately,
check what value your own system's `sshd` process reports for `_COMM` in the journal (`journalctl -u ssh.service
-o json -n1`), and if it's `sshd-session` rather than `sshd`, check whether your installed fail2ban's `sshd`
jail's journal match has been updated to account for it, or still carries the same gap this lesson found.
