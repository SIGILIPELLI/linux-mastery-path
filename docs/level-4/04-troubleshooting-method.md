---
description: "A repeatable troubleshooting method: define the symptom, scope, check changes, bisect by layer, one hypothesis at a time, and write it up."
---

# 04 · A Troubleshooting Method That Works

Experienced operators aren't faster because they know every command; they follow a method that keeps them from chasing the first theory. This lesson turns the habits scattered through earlier lessons (the connectivity checklist, the USE method, strace, reading logs) into one process you can apply to any incident, and practise on worked scenarios.

!!! note "What was run"
    This lesson is process, not tooling, and nothing in it required a Linux machine. The worked scenarios are **fictional** and use evidence of the kinds shown in earlier lessons; I did not observe them on a real system, and the numbers in them are invented to make the reasoning concrete. Where I mention tools, they are described in earlier lessons (with the run/not-run labelling given there). See Level 1 · Lesson 01.

## The loop

```text
1. Define the symptom precisely         → what is failing, for whom, since when, how often, how badly?
2. Stabilise / protect                  → stop the bleeding if users are hurt (rollback, failover, scale) but keep evidence
3. Gather evidence (don't guess yet)    → logs, metrics, recent changes, resource state
4. Scope it                             → one host or all? one user or all? one endpoint or all? one region?
5. Form hypotheses, rank by likelihood × cheapness to test
6. Test ONE hypothesis                  → make a prediction; run the check that could prove it wrong
7. Fix, verify against the original symptom, monitor
8. Write it up                          → timeline, cause, fix, how to detect sooner, how to prevent
```

### 1. Define the symptom

"The site is down" is not a symptom. "`GET /checkout` returns 502 for ~30% of requests since 14:02 UTC, only via the EU load balancer; the API health check is green" is. Capture: **what** (error text, HTTP status, exit code), **who/where** (which users, hosts, regions), **when** (first occurrence; started suddenly or gradually), **how often** (always, intermittent, periodic), and
**what normal looks like** (a baseline). Write it down; it will be your measuring stick for "fixed".

### 2. Ask what changed

Most incidents follow a change: a deploy, config push, certificate or password expiry, traffic spike, disk filling, dependency upgrade, an automatic OS update, a cloud provider event, or a **date** (cron, month-end, leap-year, DST). Check deploy logs, change tickets, `journalctl --since`, `rpm -qa --last` / `grep install /var/log/dpkg.log`, `git log`, and config-management run history (Lesson 03). "It was
working yesterday" almost always means the cause is in the last 24 hours of changes; find them before theorising.

### 3. Scope it by bisection

Binary search the system: client or server? Network or application? Which hop? Which layer? Splitting the problem space in half with each test is faster than reading code.

| Cut | Test |
|---|---|
| Is it the application or the host? | Does `curl localhost:PORT/health` work from the server itself? |
| Network or app? | `nc -zv host port` (Level 2 · 06) and `curl -v`; compare from two vantage points |
| DNS? | `getent hosts name` vs `dig @server name` (they can differ) |
| Which dependency? | Time each call in the application's logs; `strace -T` the slow call (Level 3 · 01) |
| One instance or all? | Compare a good host and a bad host: `diff` their configs, versions, kernel parameters |
| Which layer? | Walk up the stack: link, IP, route, TCP, TLS, HTTP, application, data |

**Compare good vs. bad** wherever you can. The difference between a working and failing host (package version, sysctl, mount option, clock skew) is often the cause, and tools like `diff <(ssh good 'sysctl -a') <(ssh bad 'sysctl -a')` do the work for you.

### 4. Read the evidence in the right order

1. **Errors in the logs near the first failure** (journal, application logs, `dmesg`): note the exact message and timestamp. Read *before and after* the first error; the first error is often not the loudest.
2. **Resources by USE** (Level 3 · 09): CPU, memory, disk, network, file descriptors.
3. **Metrics trends**: when did the line bend? Correlate with changes.
4. **Live process inspection**: `ss`, `lsof`, `strace`, `/proc/<pid>/` (Level 3 · 03).
5. **Packets** (`tcpdump`) when you suspect the network or a protocol-level issue.

Beware **correlated symptoms**: high load, full disk and a flood of errors are often all consequences of one earlier failure. Look for the *earliest* anomaly on the timeline.

### 5. Hypothesis discipline

For each hypothesis, ask: *What would I see if it were true? What would prove it false?* Prefer checks that are cheap, safe and decisive. Change **one thing at a time** and record it, otherwise you can't tell what worked, and you may break something else. Be suspicious of fixes that "just work" after restarting something: the restart destroyed the evidence and likely the cause remains
(a leak, a stuck lock).

### 6. Don't make it worse

- Read-only commands first. Take a snapshot or copy logs before destructive actions.
- Know your rollback before you change anything. Prefer reversible changes (config reload over restart, drain a node before rebooting it).
- On shared systems, say what you are doing (incident channel), and avoid two people changing things at once.
- Don't delete the evidence: before you clear a full disk, note what was filling it.

## Worked scenarios (fictional)

**A. "Timeouts to the database from one app server."** Symptom: 5% of requests slow (>5 s) from `app-3` only, since 09:10. Changes: none deployed; a kernel update was applied automatically at 09:00 and the host rebooted. Scope: `app-1` and `app-2` are fine, so compare `app-3` with them: a `diff` of the output of `ip link` on the good and bad hosts shows `app-3`'s interface now has a different MTU after the reboot. Prediction: large packets fail while small
ones succeed; test with `ping -M do -s 1472 db` (fails) vs `-s 1000` (works). Confirms an MTU/path-MTU problem. Fix: restore the MTU setting in network configuration; verify with the failing request. Write-up: add MTU to the config-management baseline and a post-reboot check. (The method found it: *what changed* → *compare good and bad* → *a prediction that could fail*.)

**B. "Disk full" alert at 03:00 with a deleted log.** Evidence: `df -h /var` 100%, but `du -x /var` totals only 40% of the filesystem. Hypotheses: inode exhaustion (check `df -i`: fine), files hidden under a mount point, or deleted-but-open files. `lsof +L1` lists a deleted 38 GB log held open by the application: logrotate renamed it but the app never reopened it (Level 2 · 03). Fix: restart or send the reload signal (space returns), then fix the rotation. Notice the order: it was **df vs du mismatch** that selected the hypothesis.

**C. "Random 502s every few minutes."** Periodic symptoms suggest a periodic cause: a cron job, a timer, a garbage-collection cycle, a connection pool recycling, a certificate/token refresh. Scope by correlating the 502 timestamps with `journalctl` entries and `systemctl list-timers`: if they line up with a backup timer starting, the backup's I/O or CPU use is the cause; fix by rescheduling or limiting the backup (`nice`, `ionice`, cgroup limits).

## Habits that make you faster

- Keep a **runbook** of past incidents and the commands that diagnosed them (Lesson 10).
- Maintain **dashboards for the golden signals**: latency, traffic, errors, saturation. Know what normal looks like *before* the incident.
- Practise on a lab: break things on purpose (disk full, DNS failure, killed process) and solve them against a clock.
- **Time-box** a hypothesis: if 15 minutes of work doesn't confirm or kill it, step back and re-scope.
- Escalate early when you're stuck and users are affected. Asking is fast; being the hero is slow.
- Write the timeline as you go (what you saw, what you tried, what happened): it is the postmortem.

## How It Actually Works

The method works by controlling two failure modes of human reasoning: **anchoring** (fixing on the first plausible cause) and **confirmation bias** (looking only for evidence that supports it). Requiring a prediction that could fail, one change at a time, and a baseline to compare against forces each step to add information. Bisection works because systems are layered and pipelines have a
definite order, so each test eliminates half the remaining suspects; "compare good and bad" works because most production differences are small and enumerable.

## Common mistakes

- **Starting with a theory** instead of the symptom definition.
- **Changing several things at once.**
- **Restarting first**, destroying evidence.
- **Ignoring "what changed".**
- **Trusting one tool's view** (e.g., `ping` fails so the service is down).
- **Chasing the loudest error** instead of the earliest.
- **Not comparing with a healthy peer.**
- **No write-up**, so the next incident starts from zero.

## Exercise

1. Pick a past incident you remember. Rewrite the symptom statement, list the changes in the 24 hours before it, and describe which bisection step would have found the cause fastest.
2. Break a test VM five ways (fill the disk with a deleted-but-open file, stop DNS, block a port with a DROP rule, set a wrong `fstab` entry, kill a dependency) and write the one-page diagnosis for each, including the exact commands.
3. Write a postmortem template (timeline, impact, cause, detection, fix, prevention, follow-up owners) and fill it for scenario B.
4. Time yourself solving the same synthetic fault twice, once guessing and once following the loop. Compare the times and the number of changes you made.
