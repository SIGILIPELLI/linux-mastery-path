---
description: "cron and at: the five fields, the day-of-month OR day-of-week surprise, environment pitfalls, flock, and a tested cron evaluator."
---

# 09 · Scheduling: cron, at & Timers

Backups, log rotation, certificate renewal and report generation all run on a schedule. **cron** is the oldest and most common scheduler: simple, everywhere, and full of sharp edges (a tiny environment, silent failures, overlapping runs, an infamous
day-of-week rule). This lesson makes those edges visible, and shows when to prefer systemd timers (Lesson 02).

!!! note "What was run"
    The cron daemon itself wasn't run (no Linux machine). I wrote a **Python cron-expression evaluator with 10 passing pytest tests** to *demonstrate the field semantics*; it follows Vixie/ISC cron behaviour as I understand it from `crontab(5)` and general documentation,
    and is not the real implementation. It ignores time zones and daylight-saving transitions. See Level 1 · Lesson 01.

## Anatomy of a crontab

```text
# m   h   dom mon dow   command
  30  2   *   *   *     /usr/local/bin/backup.sh
  */5 *   *   *   *     /usr/local/bin/healthcheck
  0   9   *   *   1-5   /usr/local/bin/weekday-report
  @reboot                /usr/local/bin/start-tunnel
```

Fields: minute (0-59), hour (0-23), day of month (1-31), month (1-12 or names), day of week (0-7, where both 0 and 7 mean Sunday, or names). Operators: `*` any, `,` list, `-` range, `/n` step (`*/5` every five, `10-30/10` is 10, 20, 30). Edit your table with `crontab -e`, list with
`crontab -l`; system-wide tables are `/etc/crontab` (which has an extra **user** column) and drop-in files in `/etc/cron.d/`. Scripts in `/etc/cron.daily/` etc. run via `run-parts`, and their names must not contain dots on Debian-family systems or they are silently skipped.

### Seeing what an expression means (run)

The evaluator confirms the semantics. `*/5 * * * *` matches `10:15` and not `10:16`. `30 2 * * *` after Wed 21 Oct 03:00 next fires `2026-10-22 02:30`. `0 9 * * 1-5` matches a Wednesday and not a Saturday. `0 0 * * 0` and `0 0 * * 7` select the same days. `10-30/10` is `{10, 20, 30}`.
`61 * * * *` and a four-field expression raise errors. And `0 0 30 2 *` (30 February) **never** fires; cron accepts it, and the evaluator finds no match in over two years.

### The day-of-month / day-of-week trap (run)

When **both** day-of-month and day-of-week are restricted (neither is `*`), classic cron fires when **either** matches, not both. So `0 0 13 * 5` doesn't mean "Friday the 13th"; it means "the 13th, or any Friday". The evaluator's next five matches from 1 October 2026:

```text
['Fri 2026-10-02', 'Fri 2026-10-09', 'Tue 2026-10-13', 'Fri 2026-10-16', 'Fri 2026-10-23']
```

`Tue 2026-10-13` is there because it is the 13th, and every Friday is there because it is a Friday. To get "Friday the 13th", schedule it on the 13th and test the weekday inside the script (`[ "$(date +%u)" = 5 ] || exit 0`). If you restrict only one of the two fields, the other `*` is
simply "any", and the rule is the ordinary AND.

## The environment is tiny

cron runs jobs with a minimal environment: typically `PATH=/usr/bin:/bin`, `SHELL=/bin/sh`, `HOME` set, and none of your login shell's variables or aliases. "Works in my terminal, fails in cron" is almost always this.

```text
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
MAILTO=ops@example.com
30 2 * * * cd /srv/app && ./backup.sh >> /var/log/backup.log 2>&1
```

- Use **absolute paths** for commands and files, or set `PATH` in the crontab.
- `%` in the command field means newline; escape it: `date +\%F`. (A very common silent breakage.)
- Output that isn't redirected is **mailed to the owner** (`MAILTO`); on servers with no mail system it vanishes, so redirect to a log or the journal (`| logger -t backup`).
- cron does no logging of success/failure beyond "started a job" (in syslog/journal as `CRON`); your script must log its own result and exit non-zero on failure.
- Jobs run with the user's umask and working directory `HOME`; `cd` explicitly.

## Overlaps and locking

cron starts the next run on schedule even if the previous is still going. A slow backup that takes 70 minutes on an hourly schedule will pile up. Prevent it with `flock`:

```text
*/10 * * * * flock -n /run/lock/sync.lock /usr/local/bin/sync.sh
```

`flock -n` exits immediately if another instance holds the lock. (This is Linux `util-linux`; macOS lacks `flock` by default.) Also add timeouts (`timeout 30m cmd`) so a hung job doesn't hold the lock forever, and make jobs **idempotent** so a re-run is safe.

## Time zones, DST and missed runs

cron uses the system time zone, so `30 2 * * *` has trouble on daylight-saving days: when clocks jump forward 02:30 may not exist (job skipped or run at a different time depending on the implementation), and when they go back it may happen twice. Servers should run in **UTC**, which has no DST. Also cron does not catch up on runs
missed while the machine was off (anacron handles daily/weekly jobs on laptops; systemd timers with `Persistent=true` also do, Lesson 02).

## at and batch

`at` runs a command **once**: `echo "/usr/local/bin/cleanup" | at 02:00 tomorrow`, with `atq` and `atrm` to list and remove. Good for one-off delayed tasks and the time-bomb rollback from Lesson 07.

## cron vs systemd timers

| | cron | systemd timer |
|---|---|---|
| Setup | One line | Two unit files |
| Logging | Mail or your redirect | Journal, per unit |
| Missed runs | Skipped (unless anacron) | `Persistent=true` |
| Overlap control | Manual (`flock`) | A service isn't started twice while active |
| Resource limits, sandboxing, dependencies | None | Full unit features |
| Random jitter | Manual | `RandomizedDelaySec=` |
| Portability | Everywhere (including macOS/BSD) | systemd Linux only |

Use cron for simple per-user jobs and portability; use timers for production services where logging, dependencies and limits matter.

## The evaluator

```python
"""Parse and evaluate 5-field cron expressions (minute hour day-of-month month day-of-week), with Vixie-cron semantics:
if BOTH day-of-month and day-of-week are restricted (not '*'), a day matches if EITHER matches."""
from datetime import datetime, timedelta
NAMES_M = {n: i for i, n in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}
NAMES_D = {n: i for i, n in enumerate("sun mon tue wed thu fri sat".split())}

def _field(spec, lo, hi, names=None):
    out = set()
    for part in spec.lower().split(","):
        step = 1
        if "/" in part: part, s = part.split("/"); step = int(s)
        if part in ("*", ""): a, b = lo, hi
        elif "-" in part:
            x, y = part.split("-"); a, b = (names or {}).get(x, x), (names or {}).get(y, y); a, b = int(a), int(b)
        else:
            a = int((names or {}).get(part, part)); b = hi if step != 1 else a
        if a < lo or b > hi or a > b: raise ValueError(f"value out of range in {spec!r} ({lo}-{hi})")
        out.update(range(a, b + 1, step))
    return out

class Cron:
    def __init__(self, expr):
        f = expr.split()
        if len(f) != 5: raise ValueError("need exactly 5 fields")
        self.dom_star, self.dow_star = f[2].startswith("*"), f[4].startswith("*")
        self.min, self.hour = _field(f[0], 0, 59), _field(f[1], 0, 23)
        self.dom, self.mon = _field(f[2], 1, 31), _field(f[3], 1, 12, NAMES_M)
        d = _field(f[4], 0, 7, NAMES_D); self.dow = {x % 7 for x in d}        # 7 is also Sunday
    def day_ok(self, t):
        dom_ok, dow_ok = t.day in self.dom, (t.isoweekday() % 7) in self.dow
        if not self.dom_star and not self.dow_star: return dom_ok or dow_ok     # the surprising OR rule
        return dom_ok and dow_ok
    def matches(self, t):
        return t.minute in self.min and t.hour in self.hour and t.month in self.mon and self.day_ok(t)
    def next_after(self, t, limit_days=400):
        t = t.replace(second=0, microsecond=0) + timedelta(minutes=1)
        end = t + timedelta(days=limit_days)
        while t < end:
            if self.matches(t): return t
            t += timedelta(minutes=1)
        return None
```

```text
10 passed in 0.70s
```

The tests include the OR rule, name and step parsing, the "Sunday is 0 or 7" case, and invalid input. In writing it I had to implement the OR rule explicitly: a naive implementation that ANDs every field gets `0 0 13 * 5` wrong, which is the same
mistake humans make reading the expression.

## How It Actually Works

The cron daemon wakes once a minute, reads (and caches by modification time) all the crontabs, and for each entry whose five fields match the current minute it `fork`s a child that switches to the owner's UID, sets the minimal environment and `exec`s `/bin/sh -c "<command>"`. It doesn't wait for children, which is why overlaps happen, and it
captures stdout/stderr to mail the owner. Because matching is by wall-clock minute, the clock jumping (NTP step, DST) can skip or repeat minutes; modern implementations try to compensate for small jumps.

## Common mistakes

- **Relying on your shell's `PATH` or aliases.**
- **Unescaped `%`.**
- **No output redirection**, so failures vanish or fill a mailbox.
- **Misreading the day-of-month/day-of-week OR rule.**
- **Overlapping long jobs** with no lock.
- **Scheduling at 02:00 to 03:00 local time** on DST systems.
- **Editing `/etc/cron.daily` scripts with a dot in the filename** and wondering why they never run.
- **Using cron for something that must run exactly once cluster-wide** (every node runs it).

## Exercise

1. Use the evaluator to list the next four runs of `0 9 1,15 * mon`, predict them by hand first, and explain each.
2. Add DST awareness: given a time zone, show whether `30 2 * * *` fires on the spring-forward day (Python `zoneinfo`). Document your policy.
3. On Linux, write a crontab entry that runs a script every 15 minutes with a lock, a timeout and logging to the journal; trigger it and verify with `journalctl -t`.
4. Convert that job to a systemd timer + service and list three behaviours that change.
