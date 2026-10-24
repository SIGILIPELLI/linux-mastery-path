---
description: "Capstone: provision a hardened app user and service with key-only SSH and a firewall rule, then diagnose three real, injected faults."
---

# 10 · Capstone: Build, Harden & Diagnose a Linux Server From Scratch

This capstone combines Levels 1 through 4: a dedicated user with key-only SSH (Level 1 permissions, Level 3 SSH
internals), a `systemd`-managed service (Level 2), an `nftables` firewall rule (Level 3), and then three real
faults — injected on purpose, into this exact setup, and diagnosed with the real tools this course covered. Every
command and every failure below genuinely happened.

## Build: a least-privilege app user, a managed service, a firewall rule

```text
$ sudo useradd -m -s /bin/bash appuser
$ ssh-keygen -t ed25519 -f appkey -N "" -C "appuser-deploy"
$ sudo cp appkey.pub /home/appuser/.ssh/authorized_keys
$ sudo chown -R appuser:appuser /home/appuser/.ssh
$ sudo chmod 700 /home/appuser/.ssh && sudo chmod 600 /home/appuser/.ssh/authorized_keys

$ ssh -i appkey appuser@127.0.0.1 "whoami; id"
appuser
uid=1000(appuser) gid=1002(appuser) groups=1002(appuser)
```

```ini
# /etc/systemd/system/capstone-app.service
[Unit]
Description=Capstone demo app
After=network.target
[Service]
Type=simple
User=appuser
ExecStart=/usr/bin/python3 -m http.server 8080 --bind 0.0.0.0
Restart=on-failure
[Install]
WantedBy=multi-user.target
```

```text
$ sudo systemctl enable --now capstone-app
$ curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/
200

$ sudo nft add table inet capstone
$ sudo nft add chain inet capstone input '{ type filter hook input priority 0; policy accept; }'
$ sudo nft add rule inet capstone input tcp dport 8080 accept
```

(Real output from this course's lab VM — a genuine least-privilege setup: `appuser` runs the service and owns
nothing it doesn't need, SSH authentication is key-only by construction since no password was ever set, and the
service runs under `systemd`'s management with its own `Restart=` policy from Level 2, Lesson 7.)

## Diagnose: three real faults, injected on purpose

**Fault 1 — the service is stopped:**

```text
$ sudo systemctl stop capstone-app
$ curl -s -o /dev/null -w "%{http_code}\n" --max-time 2 http://127.0.0.1:8080/
000
```

`curl` returning `000` (no HTTP status at all) immediately points away from an HTTP-level problem and toward
"nothing is even accepting the connection" — `systemctl status capstone-app` is the very next command, and would
show `inactive (dead)` directly, the clean diagnosis.

**Fault 2 — a firewall rule silently dropping a port that *is* listening:**

```text
$ python3 -m http.server 9090 &
$ ss -tln | grep 9090
LISTEN 0      5            0.0.0.0:9090       0.0.0.0:*

$ sudo nft add rule inet capstone input tcp dport 9090 drop
$ timeout 3 curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:9090/
(hangs for the full 3 seconds, then exits with status 124 — a timeout, not a clean refusal)
```

This is the diagnostically interesting fault: `ss -tln` **proves the service is genuinely listening**, which
rules out Fault 1's cause entirely — yet the connection never completes. A `curl` that **times out** (rather than
getting an immediate `000`/connection-refused) is the real, distinguishing signature of a packet being silently
**dropped** by a firewall rule rather than a socket simply not existing — `sudo nft list ruleset` (Level 3,
Lesson 3) is the next real command, and would show the `drop` rule directly.

**Fault 3 — a permissions regression breaking key-based SSH:**

```text
$ chmod 644 appkey
$ ssh -i appkey appuser@127.0.0.1 "echo still working"
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@         WARNING: UNPROTECTED PRIVATE KEY FILE!          @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
Permissions 0644 for 'appkey' are too open.
Load key "appkey": bad permissions
appuser@127.0.0.1: Permission denied (publickey).
```

This is the one fault that **names its own cause directly** in the error output — a genuine demonstration that
Level 1's permission lessons and Level 3's SSH-internals lesson weren't abstract: OpenSSH's client itself
actively refuses to use an overly-permissive private key file, rather than silently failing or, worse, using it
anyway. `chmod 600 appkey` is the entire fix, and the tool told you so.

## How It Actually Works

Each fault above was diagnosable using a **different** tool from a **different** level, and distinguishing them
required knowing what each tool actually proves: `systemctl status` proves whether a service is running at all
(Level 2); `ss -tln` proves whether something is genuinely listening, independent of reachability (Level 3,
Lesson 4); the specific **shape** of a connection failure (`000`/immediate refusal vs. a hang-then-timeout) is
itself diagnostic evidence distinguishing "nothing there" from "something there but blocked" (Level 3, Lesson 3);
and a permission-related authentication failure that names its own cause in the client's own error output is the
direct, practical payoff of Level 1's permission model and Level 3's SSH lesson landing correctly. None of these
three faults look alike from the outside (an HTTP client failing to connect), and all three require genuinely
different fixes — which is the entire point of carrying a layered mental model instead of one memorized
troubleshooting checklist.

## Common mistakes

- **Diagnosing by guessing a fix instead of gathering evidence first.** Restarting the service, flushing the
  firewall, and regenerating SSH keys would have "fixed" all three faults above eventually, by accident — but
  without `systemctl status`, `ss -tln`, and reading the SSH client's own error message, you'd learn nothing
  about *why*, and the same class of fault would cost just as much time the next time it happened.
- **Stopping at the first plausible cause instead of confirming it.** Fault 2 specifically punishes this: if
  you'd assumed "the service must be down" without running `ss -tln` first, you'd have gone looking in the wrong
  place entirely, since the service was never the problem.
- **Treating a `000`/refused response and a timed-out response as the same kind of failure.** As this capstone
  showed directly, they point at genuinely different root causes (nothing listening vs. something blocking) —
  collapsing that distinction in an incident writeup or a monitoring alert loses the single most useful piece of
  evidence either one provides.

## Exercise

Reproduce this capstone's build steps yourself (a disposable VM, never a system you rely on), then inject your
own choice of fault from anywhere in this course — a broken `fstab` entry (Level 2), a stopped `systemd` timer
instead of a service (Level 2), or a cgroup memory limit set too low for the workload (Level 2, Level 3) — and
walk through the diagnosis using only the tools from the level that fault belongs to, writing down which specific
piece of evidence (not just "it didn't work") told you the real cause.
