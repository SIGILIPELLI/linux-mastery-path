---
description: "Write systemd services and timers: Type=, Restart=, User=, sandboxing, drop-ins, OnCalendar, plus a tested unit-file linter."
---

# 02 · systemd Units, Services & Timers

A service unit is a short text file that tells systemd how to run your program: which command, as whom, how to restart it, what must start first, and how much of the machine it may touch. Writing
good units is the difference between a process you start by hand in a terminal and a service that survives reboots and crashes.

!!! note "What was run"
    systemd runs only on Linux, so **no unit was started or verified with systemd**. Option names and defaults are from the systemd man pages (`systemd.service(5)`, `systemd.timer(5)` on man7.org, October 2026). The
    **linter below is plain Python and was run on macOS** with a pytest suite (11 tests passed); it performs *static text checks I chose*, so a clean result doesn't prove systemd will accept the unit. Always run
    `systemd-analyze verify your.service` on a Linux machine. See Level 1 · Lesson 01.

## A good service unit

```ini
# /etc/systemd/system/myapp.service
[Unit]
Description=Example API
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
User=myapp
WorkingDirectory=/opt/myapp
EnvironmentFile=-/etc/myapp/env
ExecStart=/opt/myapp/bin/server --port 8080
Restart=on-failure
RestartSec=2s
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ReadWritePaths=/var/lib/myapp

[Install]
WantedBy=multi-user.target
```

### [Service] options that matter

**`Type=`** tells systemd when the service counts as started. Per the man page: `simple` (the default when `ExecStart=` is set): considered started immediately after `fork()`, before the binary is executed,
so `systemctl start` reports success even if the binary is missing; `exec`: started once the binary has been executed (usually the better choice); `forking`: the old daemon style where the
process forks and the parent exits (needs `PIDFile=` ideally); `oneshot`: runs to completion (for setup tasks, optionally `RemainAfterExit=yes`); `notify`: the service signals readiness itself via `sd_notify`;
`dbus` and `idle` are special cases.

**`Restart=`** accepts `no` (the default), `on-success`, `on-failure`, `on-abnormal`, `on-watchdog`, `on-abort`, `always`. A restart is *not* triggered when the stop was requested through systemd (`systemctl stop`).
`RestartSec=` defaults to **100 ms** per the man page, so a crash-looping service restarts ten times a second unless you set it; combine with `StartLimitIntervalSec=`/`StartLimitBurst=` to give up after repeated failures.
`on-failure` is the sensible default for long-running services.

**Identity and environment:** `User=`/`Group=` (don't run as root), `DynamicUser=yes` (a transient unprivileged user allocated at start), `WorkingDirectory=`, `Environment=`, `EnvironmentFile=`
(a leading `-` ignores a missing file). `ExecStart=` must start with an **absolute path**, and systemd does **not** run a shell: pipes, redirects, `&&` and `$VAR` expansion don't work as in a terminal (use
`/bin/sh -c '...'`, or let the unit's logging go to the journal by default).

**Lifecycle hooks:** `ExecStartPre=`, `ExecStartPost=`, `ExecReload=`, `ExecStop=`, `TimeoutStartSec=`, `TimeoutStopSec=`, `KillMode=` (default `control-group`: kill all processes in the service's cgroup).

**Sandboxing** (cheap, high value): `NoNewPrivileges=yes`, `ProtectSystem=strict` (read-only filesystem except `ReadWritePaths=`), `ProtectHome=yes`, `PrivateTmp=yes`, `PrivateDevices=yes`,
`CapabilityBoundingSet=`, `RestrictAddressFamilies=`, `SystemCallFilter=`. `systemd-analyze security myapp.service` scores a unit's exposure. A service that only needs to serve HTTP should not be able to read `/home`.

### Overriding without editing: drop-ins

```bash
sudo systemctl edit myapp         # opens /etc/systemd/system/myapp.service.d/override.conf
```

```ini
[Service]
Environment=LOG_LEVEL=debug
ExecStart=
ExecStart=/opt/myapp/bin/server --port 9090
```

For list-type options like `ExecStart=`, assigning an empty value first **clears** the inherited list; without that line you'd get two `ExecStart=` entries and an error.

## Timers instead of cron

A timer unit activates a service unit (same name by default). `OnCalendar=` uses wall-clock times; `OnBootSec=`/`OnUnitActiveSec=` use monotonic intervals.

```ini
# /etc/systemd/system/backup.timer
[Unit]
Description=Nightly backup

[Timer]
OnCalendar=*-*-* 02:30:00
Persistent=true
RandomizedDelaySec=10m

[Install]
WantedBy=timers.target
```

Per `systemd.timer(5)`: `Persistent=true` stores the last trigger time on disk, so if the machine was off when the timer should have fired, the service runs **immediately at next activation** (catch-up, useful for laptops and
cheap VMs); `AccuracySec=` defaults to **1 min**, so a timer may fire up to a minute late to coalesce wakeups; `RandomizedDelaySec=` spreads load across many machines. Enable with `systemctl enable --now backup.timer` (enable the *timer*,
not the service), and inspect with `systemctl list-timers`. `systemd-analyze calendar '*-*-* 02:30:00'` shows when a calendar expression next elapses (on Linux). Compared with cron (Lesson 09) timers give logging
in the journal, dependency handling, resource limits, and no silent mail failures, at the cost of two files.

## A tested unit-file linter (run)

The linter parses the INI-like unit with Python's `configparser` and applies the checks above. It's small enough to read in a minute.

```python
"""Lint a systemd .service unit file for common mistakes. Static checks only: not a replacement for `systemd-analyze verify`."""
import configparser, os, re, sys

def parse(text):
    cp = configparser.ConfigParser(strict=False, interpolation=None, delimiters=("=",))
    cp.optionxform = str                                   # keys are case-sensitive in unit files
    cp.read_string(text)
    return cp

def lint(text):
    problems = []
    cp = parse(text)
    for sec in ("Unit", "Service", "Install"):
        if sec not in cp: problems.append(f"missing [{sec}] section")
    svc = cp["Service"] if "Service" in cp else {}
    install = cp["Install"] if "Install" in cp else {}
    stype = svc.get("Type", "simple")
    exec_start = svc.get("ExecStart", "")
    if not exec_start and stype != "oneshot": problems.append("no ExecStart= (required unless Type=oneshot)")
    if exec_start:
        prog = exec_start.lstrip("-@+!:").split()[0] if exec_start.split() else ""
        if not prog.startswith("/"): problems.append(f"ExecStart= must start with an absolute path, got {prog!r}")
        if re.search(r"[|;&]|>>?|<", exec_start): problems.append("ExecStart= uses shell syntax (| ; & >); systemd does not run a shell, wrap it with /bin/sh -c")
    if stype == "forking" and "PIDFile" not in svc: problems.append("Type=forking without PIDFile= (systemd may guess the main PID wrong)")
    if stype in ("simple", "exec", "notify", "forking", "idle") and svc.get("Restart") is None: problems.append("no Restart= policy (default is no restart)")
    if svc.get("Restart") == "always" and "RestartSec" not in svc: problems.append("Restart=always without RestartSec= (default 100ms can make a crash loop spin; also check StartLimit*)")
    if "User" not in svc and "DynamicUser" not in svc: problems.append("no User= or DynamicUser=: the service runs as root")
    hardening = [k for k in ("NoNewPrivileges", "ProtectSystem", "ProtectHome", "PrivateTmp", "CapabilityBoundingSet", "ReadWritePaths") if k in svc]
    if len(hardening) < 2: problems.append("little sandboxing: consider NoNewPrivileges=, ProtectSystem=, PrivateTmp=, ProtectHome=")
    if "WantedBy" not in install and "RequiredBy" not in install: problems.append("[Install] has no WantedBy=/RequiredBy=: `systemctl enable` will do nothing")
    wd = svc.get("WorkingDirectory")
    if wd and not wd.lstrip("-~").startswith(("/", "~")): problems.append(f"WorkingDirectory= should be absolute, got {wd!r}")
    return problems

if __name__ == "__main__":
    probs = lint(open(sys.argv[1]).read())
    print("\n".join(probs) if probs else "OK")
    sys.exit(1 if probs else 0)
```

The tests (pytest) create a good unit and mutate it one way at a time:

```python
from unitlint import lint

GOOD = """[Unit]
Description=Example API
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
User=myapp
ExecStart=/opt/myapp/bin/server --port 8080
Restart=on-failure
RestartSec=2s
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ReadWritePaths=/var/lib/myapp

[Install]
WantedBy=multi-user.target
"""

def has(problems, needle): return any(needle in p for p in problems)

def test_good_unit_is_clean(): assert lint(GOOD) == []
def test_relative_exec(): assert has(lint(GOOD.replace("/opt/myapp/bin/server", "server")), "absolute path")
def test_shell_syntax(): assert has(lint(GOOD.replace("--port 8080", "--port 8080 > /var/log/x.log")), "shell syntax")
def test_runs_as_root(): assert has(lint(GOOD.replace("User=myapp\n", "")), "runs as root")
def test_dynamic_user_ok(): assert not has(lint(GOOD.replace("User=myapp", "DynamicUser=yes")), "runs as root")
def test_no_install(): assert has(lint(GOOD.replace("WantedBy=multi-user.target", "")), "enable")
def test_missing_restart(): assert has(lint(GOOD.replace("Restart=on-failure\n", "")), "Restart=")
def test_always_without_sec():
    u = GOOD.replace("Restart=on-failure", "Restart=always").replace("RestartSec=2s\n", "")
    assert has(lint(u), "RestartSec")
def test_forking_pidfile(): assert has(lint(GOOD.replace("Type=exec", "Type=forking")), "PIDFile")
def test_oneshot_without_exec_ok():
    u = "[Unit]\nDescription=x\n[Service]\nType=oneshot\nUser=x\nNoNewPrivileges=yes\nPrivateTmp=yes\n[Install]\nWantedBy=multi-user.target\n"
    assert not has(lint(u), "ExecStart")
def test_sandboxing_hint(): assert has(lint("[Unit]\nDescription=x\n[Service]\nUser=a\nExecStart=/bin/true\nRestart=no\n[Install]\nWantedBy=multi-user.target\n"), "sandboxing")
```

```text
11 passed in 0.01s
```

Running it on a deliberately bad unit (`ExecStart=myapp | tee /tmp/log`, `Restart=always`, nothing else):

```text
missing [Install] section
ExecStart= must start with an absolute path, got 'myapp'
ExecStart= uses shell syntax (| ; & >); systemd does not run a shell, wrap it with /bin/sh -c
Restart=always without RestartSec= (default 100ms can make a crash loop spin; also check StartLimit*)
no User= or DynamicUser=: the service runs as root
little sandboxing: consider NoNewPrivileges=, ProtectSystem=, PrivateTmp=, ProtectHome=
[Install] has no WantedBy=/RequiredBy=: `systemctl enable` will do nothing
```

While building it, my first version of the "no Restart= policy" check had a bug: it only applied to `Type=simple`, so the test unit (`Type=exec`) wasn't checked and the test for it failed. The tests caught my
mistake, not systemd's: a reminder that a linter's rules are just assumptions you've written down. Real tools to use as well: `systemd-analyze verify`, `systemd-analyze security`, and unit file review in code review.

## How It Actually Works

On `systemctl start myapp`, systemd forks, sets up the child before `exec`: it creates the service's **cgroup**, applies `User=`, namespaces and mounts for the sandboxing options (`ProtectSystem=` and `PrivateTmp=`
are implemented with mount namespaces; Level 3 · 06), sets resource limits and the environment, then executes `ExecStart=`. It connects stdout/stderr to the journal. When the main process exits, systemd consults
`Restart=` and the rate limit. A timer is simply a unit that systemd re-arms with an in-process event loop: when it elapses, it starts the associated service unit, recording the time for `Persistent=`.

## Common mistakes

- **Shell syntax in `ExecStart=`** (pipes, redirects, `~`, `$HOME`).
- **A relative path to the program.**
- **`Type=forking` for programs that don't daemonise**, or `Type=simple` for programs that do (systemd thinks it exited).
- **`Restart=always` with no `RestartSec`** so a bad deploy hammers a dependency.
- **Running as root** because it was easier.
- **Enabling the service when you wanted the timer** (or both: the service then runs at boot too).
- **Not running `daemon-reload`.**

## Exercise

1. Run the linter and tests. Add two rules of your own (for example `LimitNOFILE` present for network servers; `TimeoutStopSec` set for slow-shutdown programs), each with a failing test first.
2. On Linux, write a oneshot service and a timer that runs it every 15 minutes; check `systemctl list-timers` and `journalctl -u`.
3. Take a vendor service on your system and use `systemd-analyze security` to find the three options that would reduce its exposure most; test one in a drop-in.
4. Explain why `Persistent=true` matters for a daily timer on a laptop, and what could go wrong when catch-up runs overlap normal runs.
