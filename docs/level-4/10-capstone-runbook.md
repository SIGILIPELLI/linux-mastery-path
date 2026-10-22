---
description: "Capstone: a production runbook for a Linux service as data, validated by a tested checker for safe diagnostics, mitigations and escalation."
---

# 10 · Capstone — A Production Runbook & Checker

A runbook is the document an on-call engineer opens at 3 a.m. when an alert fires. Written well, it turns an incident into a procedure: what the alert means, what to check first, how to limit the damage, when to ask for help, and how to know it's over. This capstone draws on every level: you'll write a runbook for a fictional service as structured data, and a checker that enforces the rules a good runbook must follow.

!!! note "What was run"
    The runbook file, the checker and its **11 pytest tests were run on macOS** (Python, PyYAML). The service (`checkout-api`), tool names (`deployctl`, `lbctl`), thresholds and teams are **fictional**. The commands in the runbook are standard Linux commands from earlier lessons (most of them Linux-only and not run here); the checker validates the runbook's *structure and safety rules*, not whether a command is correct or the procedure
    works. A runbook must be exercised on a real system before anyone relies on it. See Level 1 · Lesson 01.

## What a runbook must answer

| Section | Question for the person on call |
|---|---|
| **Service header** | Who owns this? Who is on call? What's the SLO? What does it depend on? |
| **Alert → runbook link** | What does this alert mean, how severe is it, and where's the procedure? |
| **Symptom** | What will users or dashboards show? |
| **First checks** | What read-only commands tell me what's happening, and what do good and bad output look like? |
| **Scope** | One node or all? When did it start? What changed? (Lesson 04) |
| **Mitigations** | How do I reduce harm *now*, at what risk, and how do I undo each step? |
| **Escalation** | When do I stop and who do I call? |
| **Verification** | How do I know it's fixed? |
| **After** | What follow-up (postmortem, ticket, fix) is required? |

Three principles. **Diagnose read-only first**: nothing in the first checks should change the system. **Every mitigation states its risk and its undo**: you must know how to back out. **Mitigate before you root-cause**: restoring service (roll back, drain a node, fail over) usually comes before understanding the bug.

## The runbook as data

```yaml
service: checkout-api
owner: platform-team
oncall_rotation: checkout-primary
slo: {availability: "99.9% monthly", latency_p99_ms: 800}
dependencies: [postgres-primary, redis-cache, payments-gateway]
alerts:
  - name: HighErrorRate
    detection: "5xx ratio > 2% for 5 minutes"
    severity: SEV2
    runbook: high-error-rate
  - name: DiskFilling
    detection: "root or /var filesystem predicted full within 4 hours"
    severity: SEV3
    runbook: disk-filling
runbooks:
  high-error-rate:
    symptom: "Users get HTTP 502/503 from checkout-api"
    first_checks:
      - {cmd: "systemctl status checkout-api", expect: "active (running); note restarts and exit codes"}
      - {cmd: "journalctl -u checkout-api --since '30 min ago' -p err", expect: "first error and its timestamp"}
      - {cmd: "ss -ltn sport = :8080", expect: "Recv-Q well below Send-Q (accept queue not overflowing)"}
      - {cmd: "curl -s -o /dev/null -w '%{http_code} %{time_total}\n' http://localhost:8080/health", expect: "200 in < 0.2 s"}
    scope: "Compare one healthy and one failing node; check the last deploy time"
    mitigations:
      - {action: "Roll back to the previous release", cmd: "deployctl rollback checkout-api --to previous", risk: low, undo: "deployctl release checkout-api --version <current>"}
      - {action: "Drain the failing node from the load balancer", cmd: "lbctl drain <node>", risk: low, undo: "lbctl undrain <node>"}
    escalate_if: "No improvement 15 minutes after mitigation, or data loss is suspected"
    escalate_to: platform-lead
    verify: "5xx ratio below 0.5% for 10 minutes"
    after: "Open a postmortem for any SEV1 or SEV2"
  disk-filling:
    symptom: "df shows a filesystem above 85% or growing fast"
    first_checks:
      - {cmd: "df -h; df -i", expect: "which filesystem, blocks vs inodes"}
      - {cmd: "du -xh --max-depth=1 /var | sort -h | tail", expect: "largest directories"}
      - {cmd: "lsof +L1", expect: "deleted files still held open"}
    scope: "One host or the fleet? Did log volume or traffic change?"
    mitigations:
      - {action: "Make the process reopen its log", cmd: "systemctl kill -s HUP checkout-api", risk: low, undo: "none needed"}
      - {action: "Vacuum the journal", cmd: "journalctl --vacuum-size=500M", risk: medium, undo: "journal entries deleted cannot be restored"}
    escalate_if: "Free space under 5% and still dropping"
    escalate_to: platform-lead
    verify: "usage back under 80% and stable for 30 minutes"
    after: "Fix log rotation or retention so it cannot recur"
```

Where each part comes from in the course:

- First checks use `systemctl status` (Level 2 · 01), `journalctl` (Level 2 · 03), `ss -ltn` for accept-queue overflow (Level 3 · 08), a timed `curl` (Lesson 07), and for disks `df -h; df -i`, `du -x` and `lsof +L1` (Lesson 06).
- The `expect` strings are what turns a command into evidence: "Recv-Q well below Send-Q" tells the reader what to look for.
- The disk mitigation "make the process reopen its log" is the HUP fix for rotation by rename (Level 2 · 03); vacuuming the journal is flagged `medium` risk because deleted journal entries cannot be restored.
- `escalate_if` gives an objective trigger, not "if you're unsure".

## The checker

```python
"""Check an operations runbook file for completeness and safety. A review aid: it checks structure and a few safety rules, not whether the commands are right."""
import re, sys, yaml
REQUIRED_SERVICE = ("service", "owner", "oncall_rotation", "slo", "dependencies", "alerts", "runbooks")
REQUIRED_RUNBOOK = ("symptom", "first_checks", "scope", "mitigations", "escalate_if", "escalate_to", "verify", "after")
DESTRUCTIVE = re.compile(r"\brm\s+-rf\b|\bmkfs\b|\bdd\s+if=|\bDROP\s+(TABLE|DATABASE)\b|\bdelete\s+from\b|\btruncate\b|\bshutdown\b|\breboot\b|\bkill\s+-9\b|>\s*/dev/sd", re.I)
SEVERITIES = {"SEV1", "SEV2", "SEV3", "SEV4"}

def check(doc):
    problems = []
    for k in REQUIRED_SERVICE:
        if k not in doc: problems.append(f"missing top-level field '{k}'")
    rbs = doc.get("runbooks", {})
    names = set(rbs)
    for a in doc.get("alerts", []):
        if a.get("severity") not in SEVERITIES: problems.append(f"alert {a.get('name')}: severity must be one of {sorted(SEVERITIES)}")
        if not a.get("detection"): problems.append(f"alert {a.get('name')}: no detection condition")
        if a.get("runbook") not in names: problems.append(f"alert {a.get('name')}: references unknown runbook {a.get('runbook')!r}")
    linked = {a.get("runbook") for a in doc.get("alerts", [])}
    for n in names - linked: problems.append(f"runbook {n}: no alert links to it")
    for n, rb in rbs.items():
        for k in REQUIRED_RUNBOOK:
            if not rb.get(k): problems.append(f"runbook {n}: missing '{k}'")
        for c in rb.get("first_checks", []):
            if not c.get("expect"): problems.append(f"runbook {n}: check {c.get('cmd')!r} has no 'expect' (what does good/bad look like?)")
            if DESTRUCTIVE.search(c.get("cmd", "")): problems.append(f"runbook {n}: first_checks must be read-only, found {c['cmd']!r}")
        for m in rb.get("mitigations", []):
            for f in ("action", "cmd", "risk", "undo"):
                if not m.get(f): problems.append(f"runbook {n}: mitigation {m.get('action')!r} missing '{f}'")
            if m.get("risk") not in ("low", "medium", "high"): problems.append(f"runbook {n}: mitigation {m.get('action')!r} has invalid risk {m.get('risk')!r}")
            if DESTRUCTIVE.search(m.get("cmd", "")) and m.get("risk") != "high": problems.append(f"runbook {n}: destructive command {m['cmd']!r} must be marked risk: high")
            if m.get("risk") == "high" and "approval" not in m: problems.append(f"runbook {n}: high-risk mitigation {m.get('action')!r} needs an 'approval' field")
        if len(rb.get("first_checks", [])) < 2: problems.append(f"runbook {n}: fewer than two diagnostic checks")
    return problems

if __name__ == "__main__":
    p = check(yaml.safe_load(open(sys.argv[1]))); print("\n".join(p) if p else "OK"); sys.exit(1 if p else 0)
```

Tests (11 passing) start from the valid runbook and apply one mutation each: remove the owner; point an alert at an unknown runbook; leave a runbook with no alert (an orphan nobody will find); an invalid severity; a check with no `expect`; a **destructive command smuggled into the "first checks"** (`rm -rf /var/log/*`); a mitigation without an `undo`; a destructive mitigation marked low risk (`truncate`); a high-risk
mitigation (`systemctl reboot`) without an `approval`; and no escalation target. All eleven pass, which means each mutation is caught by exactly the rule written for it, and the original is clean.

On a copy of the runbook where I removed one `undo` and blanked both `escalate_to` fields, the checker printed:

```text
runbook high-error-rate: missing 'escalate_to'
runbook disk-filling: missing 'escalate_to'
runbook disk-filling: mitigation 'Make the process reopen its log' missing 'undo'
```

Limits to keep in mind: the destructive-command detector is a **regex denylist** (it misses anything creative, and might flag harmless text), so it supplements human review, never replaces it. It cannot tell whether `deployctl rollback` is the right command, whether the thresholds are sensible, or whether the escalation contact is reachable. The best validation is an **exercise**: run the runbook as a game day against a staging system.

## Your capstone

Produce for a service you know (or invent one) a complete operations package, and test it:

1. **Runbook file** like the one above with at least three alerts (a resource, a dependency, an application symptom), passing the checker. Add two rules to the checker of your own (for example, every alert must have a `dashboard` link; every mitigation with `risk: medium` must say who can approve it).
2. **A fault matrix**: for each runbook, the fault you would inject on a test VM to exercise it (fill the disk, kill the database, drop port 443 with a firewall DROP, break `fstab`, exhaust file descriptors, delete an open log).
3. **A hardened baseline**: the configuration of the VM passing the Level 2 hardening linter and the Level 4 container/unit linters with zero HIGH findings, kept in version control and applied by automation (Lesson 03).
4. **Backup and restore proof**: a documented, timed restore drill (Lesson 02) with the manifest verification.
5. **Patch plan**: how and when the service's hosts get security updates and reboots without downtime (Lesson 05).
6. **Monitoring**: which USE signals (Level 3 · 09) and application SLIs you alert on, with thresholds, and which `/proc`-based indicators the Level 3 monitor would add.
7. **Postmortem template** filled in for one injected fault, with timeline, detection time, mitigation, cause, and follow-ups.
8. **Unknowns**: what you could not test (be candid, as this course tries to be).

## Exercise

1. Run the checker on the sample runbook, then add a third runbook (a dependency failure such as the database being unreachable) with at least three read-only checks and two mitigations, and make it pass.
2. Mutate your runbook in two new ways the checker does not yet catch, then add a rule and a test for each.
3. Run a game day: inject one fault from your fault matrix on a test VM and have someone else follow the runbook. Record every place they hesitated or had to guess, and fix the runbook.

## How It Actually Works

A runbook-as-data is a policy engine over a declarative model, the same pattern as the governance linter (Databricks course Level 3), the hardening linter (Level 2 · 10) and the configuration-management library (Lesson 03): represent decisions as structured records, express rules as small functions over them, and run them in CI so that reviewing a runbook is a pull request with failing checks instead of a meeting. The leverage comes from the model: because mitigations
have explicit `risk`, `undo` and `approval` fields, rules like "destructive commands must be high risk" are five lines. The limit is the same as ever: anything not in the model is invisible to the rules.

## Common mistakes

- **Runbooks nobody exercises**, which rot as the system changes.
- **Free-text prose** with no expected outputs ("check the logs").
- **Mitigations with no undo** or unstated risk.
- **Diagnostics that change state.**
- **No escalation criteria**, or escalation to a person rather than a rotation.
- **Alerts without runbooks** (and runbooks without alerts).
- **Skipping verification** so incidents are closed on hope.
- **Treating the checker as the review.**

## Where to go next

You now have a mental model of Linux from the kernel boundary to production operations, and a habit of testing claims. Strong next steps: build a three-VM lab (web, database, bastion) and inject the faults from your matrix; learn Ansible and Terraform to apply Lessons 03 and the hardening baseline at scale (the Ansible and Terraform courses in this series cover them as they appear); read the Linux man pages cited in these
lessons for the commands you rely on; study one subsystem deeply (networking with `tcpdump` and netfilter, or storage with `fio`); and rehearse incident response with game days. Kernel versions, distribution defaults and tool options keep changing, so re-check anything in this course against your own systems.
