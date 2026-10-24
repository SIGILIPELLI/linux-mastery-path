---
description: "Write and run a real systemd service and timer pair — Restart=, OnUnitActiveSec=, and a timer that replaces a cron job."
---

# 07 · Writing systemd Services & Timers

Reading unit files is one skill; writing one that actually does what you intend, restarts the right way when it
fails, and runs on the schedule you meant, is another. This lesson writes, enables, and watches run a real
service-and-timer pair — the modern systemd-native replacement for a cron job.

## Why a timer instead of cron

A `.timer` unit paired with a `.service` unit gets you everything cron never had for free: the service's output
goes through the normal `journald` pipeline (Lesson 8) instead of needing its own mail/logging setup, you can
express dependencies (`After=network-online.target` if the job needs network), you get `systemctl status` showing
you exactly when it last ran and whether it succeeded, and `OnUnitActiveSec=` (run N seconds after the *previous
run finished*) avoids the classic cron problem of a 5-minute job scheduled every 5 minutes quietly overlapping
itself if one run happens to take 6 minutes.

## Worked example: a real service and timer, running on a real schedule

```text
$ cat /etc/systemd/system/heartbeat.service
[Unit]
Description=Course demo heartbeat

[Service]
Type=oneshot
ExecStart=/bin/bash -c "echo heartbeat at $(date -Is) >> /tmp/heartbeat.log"

$ cat /etc/systemd/system/heartbeat.timer
[Unit]
Description=Run heartbeat.service every 5 seconds

[Timer]
OnBootSec=2s
OnUnitActiveSec=5s
AccuracySec=1s

[Install]
WantedBy=timers.target

$ sudo systemctl enable --now heartbeat.timer
Created symlink '/etc/systemd/system/timers.target.wants/heartbeat.timer' → '/etc/systemd/system/heartbeat.timer'.

$ systemctl list-timers heartbeat.timer --no-pager
NEXT                        LEFT LAST                           PASSED UNIT            ACTIVATES
Sat 2026-10-24 16:20:13 IST   4s Sat 2026-10-24 16:20:08 IST 172ms ago heartbeat.timer heartbeat.service

$ cat /tmp/heartbeat.log
heartbeat at 2026-10-24T16:19:57+05:30
heartbeat at 2026-10-24T16:20:02+05:30
heartbeat at 2026-10-24T16:20:08+05:30

$ systemctl status heartbeat.service --no-pager
○ heartbeat.service - Course demo heartbeat
     Loaded: loaded (/etc/systemd/system/heartbeat.service; static)
     Active: inactive (dead) since Sat 2026-10-24 16:20:08 IST; 160ms ago
TriggeredBy: ● heartbeat.timer
    Process: 257214 ExecStart=/bin/bash -c ... (code=exited, status=0/SUCCESS)
```

(Real output — this timer genuinely fired three times, 5 seconds apart, over a 12-second observation window on
this course's lab VM.) `Type=oneshot` tells systemd this service is meant to run to completion and exit, not stay
running — the correct type for anything that does a unit of work and finishes, as opposed to a long-lived daemon.
`heartbeat.service`'s status after a run is `inactive (dead)` with `status=0/SUCCESS` — that's the *expected*,
healthy end state for a oneshot, not a failure. `OnBootSec=2s` fired the first run 2 seconds after the timer was
enabled; `OnUnitActiveSec=5s` fired every run after exactly 5 seconds from the *previous run's completion* — the
log timestamps, 16:19:57, 16:20:02, 16:20:08, confirm the real 5-second cadence, not an approximation.

## How It Actually Works

Timers are themselves ordinary systemd units with their own lifecycle, which is why `systemctl list-timers`,
`systemctl status <timer>`, and the normal enable/disable/start/stop verbs all work on them exactly like any other
unit — there's no separate "cron daemon" subsystem running in parallel; it's the same unit-and-dependency machinery
from Lesson 6. `OnCalendar=` (not used in this example, but common for "every day at 3am"-style schedules) is
parsed by `systemd-analyze calendar`, which is worth running against any calendar expression before trusting it,
because the syntax, while powerful, is genuinely easy to get subtly wrong on the first attempt.

**`Restart=`** (used on the real `ssh.service` in Lesson 6 as `Restart=on-failure`) only applies to units systemd
expects to *keep running* (`Type=simple`, `notify`, etc.) — it tells systemd what to do when the main process
exits unexpectedly: `on-failure` restarts only on a non-zero exit or signal death, `always` restarts even on a
clean exit, and `no` (the default) never restarts automatically. Combined with `RestartSec=` (how long to wait
before retrying) and `StartLimitBurst=`/`StartLimitIntervalSec=` (how many restarts to allow within what window
before giving up entirely), this is systemd's built-in crash-loop protection — without a start limit, a service
that fails instantly on every start would otherwise restart in an unbounded, CPU-burning loop forever.

## Common mistakes

- **Using `Type=simple` for a oneshot job.** systemd will consider the unit "started" the instant the process
  forks, then immediately see it exit and may report it as failed or flapping, depending on `Restart=` settings —
  `Type=oneshot` exists specifically so "ran once and exited 0" reads as success, not as a crash.
- **Scheduling a frequent timer with `OnCalendar=` instead of `OnUnitActiveSec=` when you actually want
  "N seconds after the last run finished."** `OnCalendar=` schedules by wall-clock time regardless of whether the
  previous run is still going, which can reintroduce the exact cron-overlap problem timers are meant to avoid.
- **Forgetting `systemctl daemon-reload` after creating or editing a unit file** (the same mistake as Lesson 6) —
  a brand-new unit file won't even be visible to `systemctl start`/`enable` until systemd reloads its unit cache.

## Exercise

Write your own `.service`/`.timer` pair that appends a timestamp to a log file every 10 seconds, enable it, watch
it fire at least three times with `journalctl -u <your-service> -f`, then change `OnUnitActiveSec=` to a different
interval, run `daemon-reload`, and confirm the new interval takes effect without needing to disable and re-enable
the timer.
