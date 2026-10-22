---
description: "Linux logging with journald and syslog, size limits, and why renaming a log leaves the process writing to the old file, tested with real runs."
---

# 03 · Logging: journald, syslog & logrotate

Logs are how a server tells you what happened. On Linux they arrive by two main routes: the **systemd journal** (binary, structured, queried with `journalctl`) and classic **syslog text files** under
`/var/log`. Most modern distributions run both. This lesson covers reading them, controlling their size, and the file-descriptor behaviour that makes log rotation more subtle than it looks.

!!! note "What was run"
    `journalctl`, `rsyslog` and `logrotate` are Linux tools, so they were **not run**. Facts about them come from `journald.conf(5)` and related man pages (man7.org, October 2026). What *was* run, on
    **macOS**: the file-rotation and open-file-descriptor experiments below (plain POSIX behaviour, identical on Linux), and text-processing on a **hand-written syslog-format fixture** (not from a real system). See Level 1 · Lesson 01.

## Where logs live

| Source | Where | Notes |
|---|---|---|
| systemd journal | `/var/log/journal/` (persistent) or `/run/log/journal/` (volatile) | Binary; read with `journalctl` |
| Syslog text files | `/var/log/syslog` or `/var/log/messages`, `/var/log/auth.log` or `/var/log/secure`, `/var/log/kern.log` | Plain text; names vary by distribution family |
| Application logs | `/var/log/nginx/`, `/var/log/postgresql/` ... | Written by the program itself |
| Kernel ring buffer | `dmesg` / `journalctl -k` | In-memory; boot and driver messages, OOM kills |
| Audit log | `/var/log/audit/audit.log` | Security events (`auditd`; Level 4 · 08) |

Per `journald.conf(5)`, `Storage=` can be `volatile` (memory only, below `/run/log/journal`), `persistent` (on disk below `/var/log/journal`), `auto` (persistent only if `/var/log/journal` exists), or `none`.
So on a system where that directory doesn't exist the journal **is lost at reboot**, a common surprise after a crash; create the directory (or set `Storage=persistent`) on servers.

## journalctl

```bash
journalctl -u nginx                 # one unit's logs
journalctl -u nginx -b              # since this boot  (-b -1 = previous boot)
journalctl -u nginx --since "1 hour ago" --until "10 min ago"
journalctl -f                       # follow (like tail -f)
journalctl -p err -b                # priority err and worse, this boot
journalctl -k                       # kernel messages
journalctl _PID=812                 # filter by a field
journalctl -o json-pretty -n 1      # structured fields
journalctl --disk-usage ; journalctl --vacuum-size=500M ; journalctl --vacuum-time=2weeks
```

The journal stores **fields**, not just text (`_SYSTEMD_UNIT`, `_PID`, `PRIORITY`, `MESSAGE`, `_HOSTNAME`), which is what makes `journalctl -u` and field filters work without grep. Services launched by
systemd get stdout/stderr captured into the journal automatically, which is why a unit file rarely needs `> /var/log/x.log` (and why shell redirection in `ExecStart=` doesn't work; Lesson 02).

### Size limits

From the man page: `SystemMaxUse=` caps total journal disk use and `SystemKeepFree=` keeps space free; defaults are **10% and 15% of the file system respectively, each capped at 4 G**, and journald uses the smaller
effective limit. `SystemMaxFileSize=` defaults to one eighth of `SystemMaxUse=`. Only *archived* files are deleted to enforce the limits, so usage can temporarily exceed the cap. Set explicit values on small disks:

```ini
# /etc/systemd/journald.conf.d/size.conf
[Journal]
Storage=persistent
SystemMaxUse=1G
MaxRetentionSec=1month
```

## Syslog: facilities, severities and rsyslog

Classic syslog tags each message with a **facility** (`auth`, `authpriv`, `cron`, `daemon`, `kern`, `local0`-`local7`...) and a **severity**, 0 to 7:

| 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| emerg | alert | crit | err | warning | notice | info | debug |

`journalctl -p err` selects 3 and below. A daemon like `rsyslog` receives messages (from the journal or `/dev/log`) and routes them by `facility.severity` rules to files or remote servers:

```text
# /etc/rsyslog.d/50-default.conf  (typical Debian-style lines)
auth,authpriv.*      /var/log/auth.log
*.*;auth,authpriv.none  -/var/log/syslog
*.* @@logs.example.internal:514        # forward everything over TCP (double @)
```

You can emit messages from scripts with `logger -t myapp -p user.warning "disk 91% full"` (the BSD `logger` on the Mac accepted `logger -t lxdemo "..."`, though I did not capture the result in the macOS unified log).

### Reading a syslog line (fixture, hand-written)

```text
Oct 21 10:00:01 web1 sshd[812]: Failed password for invalid user admin from 203.0.113.5 port 52814 ssh2
Oct 21 10:00:03 web1 sshd[812]: Failed password for invalid user admin from 203.0.113.5 port 52816 ssh2
Oct 21 10:01:10 web1 sshd[901]: Accepted publickey for deploy from 198.51.100.7 port 40022 ssh2
Oct 21 10:02:00 web1 kernel: Out of memory: Killed process 4242 (java)
Oct 21 10:02:05 web1 CRON[1000]: (root) CMD (/usr/local/bin/backup)
```

Timestamp, host, **program[pid]**, message. Note the traditional syslog timestamp has **no year and no time zone**: a classic source of confusion when correlating logs across hosts (the journal and RFC 5424 formats fix this). With the pipelines
from Level 1 · 06 (run on this fixture):

```text
awk '/Failed password/ {for(i=1;i<=NF;i++) if($i=="from") print $(i+1)}' f | sort | uniq -c    →   2 203.0.113.5
awk '{print $5}' f | sed 's/\[.*//;s/://' | sort | uniq -c | sort -rn                          →   3 sshd, 1 kernel, 1 CRON
grep -c "Failed password" f  →  2          grep -i "out of memory" f  →  the kernel OOM line (Level 3 · 02)
```

(The documentation IP addresses 203.0.113.0/24 and 198.51.100.0/24 are reserved for examples.)

## Rotation, and the open-file-descriptor trap (run)

Logs grow forever unless rotated. **logrotate** (run daily by a cron job or timer) renames, compresses and deletes old logs by policy:

```text
# /etc/logrotate.d/myapp
/var/log/myapp/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 myapp adm
    postrotate
        systemctl kill -s HUP myapp.service   # or: kill -HUP $(cat /run/myapp.pid)
    endscript
}
```

Why the `postrotate` signal? I tested what happens when a program that opened its log once (a shell loop holding `exec 3>>app.log`) is rotated by **renaming** the file:

```text
mv app.log app.log.1; touch app.log
→ new app.log lines: 0     app.log.1 lines: 24      (the writer kept writing to the renamed file!)
```

A process writes to the **open file** (the inode), not the name. After `mv`, the writer's descriptor still points at `app.log.1`; the new `app.log` stays empty and the old file keeps growing and can't be freed (Level 1 · 03). The fix is to
make the program reopen its log (hence `SIGHUP` or a `reload` in `postrotate`), or use the alternative **`copytruncate`**: copy the file, then truncate the original in place. I ran that:

```text
cp app.log app.log.2; : > app.log
→ app.log after truncate: 30 lines (the writer, using append mode, continued at the new end)   app.log.2: 10 lines
```

It works because the writer opened the file with `>>` (append mode), but anything written **between the `cp` and the truncate is lost**, and the copy of a huge file costs time and disk. Prefer programs that reopen logs on a signal, or
log to the journal/stdout and let the platform handle it. Rotation by `mv` plus a reopen signal, or by built-in rotation (nginx `USR1`, Python's `WatchedFileHandler`), is the robust pattern.

## Centralising

Production systems ship logs off the machine: `rsyslog` forwarding, `systemd-journal-remote`, or agents (Fluent Bit, Vector, Filebeat) to a log platform (Level 4). Reasons: a compromised or dead host can't be trusted to keep its own logs, and searching across hosts is
hard otherwise. Always include the host, a service name and a machine-readable timestamp with zone (RFC 3339), and avoid logging secrets.

## How It Actually Works

Programs write to `stdout`, to syslog via the `/dev/log` socket, or directly to the journal's native protocol. `systemd-journald` receives all of these, adds trusted metadata that the sender can't forge (PID, UID, unit from the cgroup), indexes it
into binary files, and forwards to syslog if configured. A text log, by contrast, is just a file with an open descriptor, and everything about rotation follows from Unix file semantics: the kernel tracks the inode, not the pathname, so rename, delete and truncate behave as the experiment above showed.

## Common mistakes

- **A journal that vanishes on reboot** (volatile storage by default when `/var/log/journal` is missing).
- **Rotating by renaming without telling the program** (empty new log, huge hidden old one).
- **`copytruncate` for high-volume logs**, losing lines.
- **No size limits** and a full `/var`.
- **Grepping text logs for time ranges** across year boundaries and time zones.
- **Logging secrets** (tokens, passwords in URLs).
- **Not forwarding logs** off the host.

## Exercise

1. Reproduce the rotation experiment. Then change the writer to reopen the file on `SIGHUP` (`trap`) and rotate correctly.
2. On Linux, find where your SSH failures are logged (`journalctl -u ssh`/`sshd`, or `/var/log/auth.log`) and count failures per source IP in the last day.
3. Write a logrotate stanza for an application that rotates at 100 MB, keeps 7 compressed copies, and reloads via `systemctl`. Test with `logrotate -d` (debug mode).
4. Compute the journal size limits your system would use with defaults, given your `/var` filesystem size, using the 10%/15% and 4G rules.
