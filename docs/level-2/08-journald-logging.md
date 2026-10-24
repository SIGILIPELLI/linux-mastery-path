---
description: "journald's structured logs vs flat-text syslog, real JSON fields from a live journal entry, and persistent vs volatile storage."
---

# 08 · Logging & journald: Structured Logs at the OS Level

Grepping a text log file for a timestamp and a process name is something every Linux user eventually does, and
`journalctl` can replace almost all of that grepping — because unlike a traditional syslog text file, each journal
entry isn't a line of text at all; it's a structured record with named fields, several of which the kernel or
systemd attached automatically, with no help from the program that logged the message.

## Worked example: one real log entry's actual structure

```text
$ journalctl -u ssh.service -o json-pretty -n 1 --no-pager
{
	"MESSAGE" : "Stopped ssh.service - OpenBSD Secure Shell server.",
	"UNIT" : "ssh.service",
	"SYSLOG_IDENTIFIER" : "systemd",
	"_COMM" : "systemd",
	"_EXE" : "/usr/lib/systemd/systemd",
	"_UID" : "0",
	"_GID" : "0",
	"_BOOT_ID" : "1e8b72759fec45ccae08682c99b4d38f",
	"_SYSTEMD_UNIT" : "init.scope",
	"_SYSTEMD_CGROUP" : "/init.scope",
	"_TRANSPORT" : "journal",
	"__MONOTONIC_TIMESTAMP" : "2081453838",
	"_SOURCE_REALTIME_TIMESTAMP" : "1792718432683583",
	"CODE_FILE" : "src/core/job.c",
	"CODE_FUNC" : "job_emit_done_message",
	"CODE_LINE" : "815"
}

$ journalctl --disk-usage
Archived and active journals take up 8M in the file system.

$ ls -la /var/log/journal
drwxr-sr-x+  3 root systemd-journal 4096 Oct 22 23:26 .
```

(Real output from this course's lab VM — one genuine log entry, with nothing trimmed from its field list except
a few internal sequence-number fields.) Notice how much of this record was **not** written by `ssh.service` or
even by the message's apparent author: `_UID`, `_GID`, `_BOOT_ID`, `_SYSTEMD_CGROUP`, `_SOURCE_REALTIME_TIMESTAMP`
were all stamped on by the journal itself at the moment the message was received, straight from kernel/process
metadata — which is exactly why `journalctl -u <unit>` can filter perfectly by unit even for programs that never
call any systemd-specific logging API: the *filtering key* comes from the environment the message was logged in,
not from parsing the text of the message. `CODE_FILE`/`CODE_FUNC`/`CODE_LINE` show that this particular message
came from a program using `sd_journal_print()`-family calls directly (which can tag source location), while a
plain program writing to stdout/stderr under a service unit still gets the unit, UID, GID, cgroup and boot-ID
fields for free, just not the source-location ones. `/var/log/journal` existing at all (as opposed to being
absent) is this system's signal that journald is configured for **persistent** storage — logs survive a reboot —
rather than the volatile-by-default `/run/log/journal`, which is wiped on every reboot.

## How It Actually Works

journald stores entries in its own **binary, indexed** file format (not plain text), which is what makes rich
filtering (`journalctl _UID=1000`, `journalctl _SYSTEMD_CGROUP=/system.slice/ssh.service`, time-range queries)
fast without re-parsing gigabytes of text on every query — closer to a lightweight structured database than a
`.log` file. It still interoperates with traditional syslog: journald can forward everything to a classic
`rsyslog`/`syslog-ng` daemon (common on systems that need, e.g., centralized log shipping with tooling that
expects flat syslog), and it accepts input not just from `sd_journal_print()`-aware programs but from anything
writing to stdout/stderr under a systemd unit, from the kernel's own ring buffer (`journalctl -k`, replacing
`dmesg` for most interactive use), and from the traditional `/dev/log` socket for programs that only know how to
speak classic syslog.

The **persistent vs. volatile** storage choice (`Storage=` in `/etc/systemd/journald.conf`, default `auto`, which
persists if `/var/log/journal` exists and is volatile otherwise) matters more than it looks like it should: a
volatile-only journal means every log from before the last reboot is simply gone — fine for a stateless container
that ships logs elsewhere immediately, a real problem if you're trying to post-mortem a crash on a server that
just restarted. `journalctl --disk-usage` and the `SystemMaxUse=`/`RuntimeMaxUse=` settings control how large the
journal is allowed to grow before journald starts rotating out old entries — unlike unbounded flat text logs that
can, in the worst case, fill a disk, journald is size-capped by design.

## Common mistakes

- **Assuming `journalctl` without filters shows "everything" usefully.** On a busy system it's an overwhelming
  firehose; `-u <unit>`, `-b` (this boot only, or `-b -1` for the previous boot), `--since`/`--until`, and `-p
  err` (priority filter) are what make it actually usable day to day.
- **Not checking whether the journal is persistent before relying on post-incident logs.** If `/var/log/journal`
  doesn't exist and `Storage=auto`, logs from before the crash that caused the reboot may already be gone by the
  time you go looking for them.
- **Forgetting that a service's own `stdout`/`stderr` go to the journal by default**, so grepping an old-style
  `/var/log/<app>.log` file for an application that was migrated to run under systemd can turn up nothing, not
  because logging stopped, but because it moved to `journalctl -u <that-service>`.

## Exercise

Run `journalctl -u ssh.service -o json-pretty -n 1` (or any service you have) on a Linux machine you control, and
identify at least three fields in the output that the *journal* attached automatically rather than the program
itself. Then check whether your system's journal is persistent (`ls /var/log/journal`) and, if it's volatile-only,
make it persistent by creating that directory with the correct ownership (`systemd-tmpfiles --create
--prefix=/var/log/journal`) and restarting `systemd-journald`.
