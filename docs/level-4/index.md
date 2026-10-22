---
description: "Linux Level 4: robust scripts, backups, configuration management, troubleshooting, patching, auditing, containers and a runbook capstone."
---

# Level 4 · Operations & Reliability

Level 4 is about running Linux machines as a responsible operator: scripts that fail safely, backups that restore, configuration that doesn't drift, a method for diagnosing faults, patching without outages, auditing for tampering and abuse, containers, and a runbook that a tired engineer can follow.

!!! note "What was run, and what wasn't"
    This course was written on a Mac, so nothing here ran on Linux. Level 4 leans on things that *are* portable and were run on macOS: shell strictness experiments (bash 3.2), `tar`, `rsync` (openrsync), checksums, disk images for the df-versus-du case, sparse files, `curl` timing and exit codes, TCP connection classification, and pytest-tested Python tools (a configuration "ensure" library, a Debian version
    comparator, a file-integrity monitor, an image layer model, a Dockerfile linter, a runbook checker). Linux-only tools (`systemctl`, `auditd`, `needrestart`, `tcpdump`, container runtimes) are described from man pages and general documentation and marked as not run. Several of my own first attempts were wrong; where a test or experiment corrected me, the lesson says so.

**Prerequisites:** Levels 1 to 3.

## Modules

1. **[Robust Shell Scripts](01-robust-shell-scripts.md)**: what `set -e`, `-u` and `pipefail` really do, tested; traps, locks, idempotence.
2. **[Backups: tar, rsync & Restore Testing](02-backups-rsync.md)**: snapshots with `--link-dest`, the size-and-mtime trap, checksums.
3. **[Automation & Configuration Management](03-automation-config.md)**: idempotent "ensure" operations, check mode, drift.
4. **[A Troubleshooting Method That Works](04-troubleshooting-method.md)**: define, scope, bisect, one change at a time.
5. **[Patching, Kernel Updates & Reboots](05-patching-kernels.md)**: backports, restarts, kernels, a tested version comparator.
6. **[Troubleshooting Disks & Filesystems](06-storage-troubleshooting.md)**: `df` vs `du`, deleted-open files, sparse files, inodes.
7. **[Troubleshooting the Network](07-network-troubleshooting.md)**: refused vs timeout vs reset vs DNS, curl timing, MTU.
8. **[Security Auditing: auditd, Lynis & Logs](08-security-auditing.md)**: audit rules, log review, file integrity monitoring.
9. **[Containers on Linux: Images, Runtimes & Limits](09-containers-on-linux.md)**: layers and whiteouts, a Dockerfile linter, PID 1.
10. **[Capstone: A Production Runbook & Checker](10-capstone-runbook.md)**: operations as data, with a safety checker.

## After the course

Re-run the experiments on a real Linux VM and compare with the macOS results; wherever the two differ, you have learned something about portability.
