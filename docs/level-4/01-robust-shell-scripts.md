---
description: "Shell scripts that fail safely: what set -e, -u and pipefail really do (tested), quoting, trap, getopts, locking and idempotence."
---

# 01 · Robust Shell Scripts

Operations work runs on shell scripts: deploys, backups, cron jobs, health checks. A script that works on the happy path and silently does damage on the unhappy one is worse than none. This lesson collects the habits that make scripts fail safely, and checks each claim against how bash actually behaves rather than how it is usually described.

!!! note "What was run"
    Every shell snippet and result below was **run on macOS**, where `/bin/bash` is **version 3.2** (a Mac-specific fact I checked; see below). `shellcheck` was not installed, so I have no shellcheck output. Behaviour is bash-specific unless marked POSIX; Linux distributions ship bash 5.x, and a few results (empty arrays under `set -u`) differ between versions, which I flag. The Shell language itself is covered in
    the [Shell Mastery Path](https://sigilipelli.github.io/shell-mastery-path/). See Level 1 · Lesson 01.

## The "strict mode" and what it really does

```bash
#!/usr/bin/env bash
set -euo pipefail
```

- `-e` (errexit): exit when a command fails. `-u` (nounset): treat unset variables as errors. `-o pipefail`: a pipeline fails if *any* stage fails (Level 1 · 06).

These help, but `-e` in particular has well-known holes. I tested them:

| Test | Result (run) | Lesson |
|---|---|---|
| `set -e; false \|\| echo handled` | printed `handled`, continued | A failure in an `\|\|` list is considered handled |
| `set -e; if false; then :; fi; echo ...` | continued | Failures in `if` conditions don't exit |
| `set -e; f() { false; echo "after false"; }; f && echo reached` | printed **`after false inside function...`** and `reached` | **`-e` is ignored inside a function called as part of an `&&`/`\|\|` list or `if` condition**: the failing `false` did not stop the function |
| `set -e; x=$(false); echo ...` | exited (rc 1) | A failing command substitution in a plain assignment does exit |
| `set -e; fn() { local v=$(false); echo "continued"; }` | printed `local masks the failure: continued` | **`local v=$(cmd)` hides the failure** (the exit status is that of `local`); declare, then assign: `local v; v=$(cmd)` |
| `set -e; echo a \| grep -q zzz` | exited, rc 1 | The last pipeline command's failure exits (grep returned 1) |

The conclusion isn't "don't use `-e`"; it's that **it is a safety net, not control flow**. For commands where you care about failure, check explicitly: `cmd || { echo "cmd failed" >&2; exit 1; }`. Never rely on `-e` inside functions that are invoked in conditions.

### -u catches typos and the `rm -rf "$DIR/"` accident

```text
set -u; echo "$UNDEFINED_VAR"        →  bash: UNDEFINED_VAR: unbound variable
DIR=""; echo rm -rf "$DIR/"          →  rm -rf /                (dry run with echo!)
set -u; DIR=""; echo rm -rf "${DIR:?DIR must be set}/"   →  bash: DIR: DIR must be set
```

An empty variable inside `rm -rf "$DIR/"` becomes `rm -rf /`. `-u` does not help when the variable is *set but empty*; `${VAR:?message}` aborts on unset **or empty**. Use it on every variable that feeds a destructive command, or validate first.

**Version trap (run):** on this Mac's bash 3.2, `set -u; arr=(); echo "${arr[@]}"` died with `arr[@]: unbound variable`. Newer bash (4.4 and later) treats an empty array as set. A script that works on Linux's bash 5 can fail on a Mac's 3.2 (and the reverse for features like `mapfile`, associative arrays, `${var,,}`, which don't exist in 3.2). State your minimum bash version, and test on it.

## Quote everything

```text
f="a b"; set -- $f    →  unquoted -> 2 args        set -- "$f"  →  quoted -> 1 arg
files=("one two" three); for f in "${files[@]}"; do echo "[$f]"; done   →  [one two] / [three]
```

Unquoted expansions are split on whitespace and glob-expanded (Level 1 · 03). Use `"$var"`, `"${array[@]}"`, `"$@"`, and `--` before user-supplied filenames (`rm -- "$f"`). Prefer arrays for lists of arguments over strings.

## Clean up with trap

```bash
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT         # runs on normal exit, on `exit N`, and on errors under -e
```

Run: `t=$(mktemp -d); trap "rm -rf $t; echo cleaned" EXIT; ...; exit 3` printed `cleaned` and exited with status 3: the trap ran and the exit status was preserved. `EXIT` traps don't run on SIGKILL (nothing can), so also design so leftover temp files are harmless. Add `trap 'echo "failed at line $LINENO" >&2' ERR` for diagnostics.
Use `mktemp`, never fixed names in `/tmp` (races and symlink attacks).

## Arguments and validation

```bash
usage() { echo "usage: $0 [-n count] [-v] file" >&2; exit 2; }
count=1; verbose=0
while getopts "n:vh" o; do case $o in n) count=$OPTARG;; v) verbose=1;; *) usage;; esac; done
shift $((OPTIND-1)); [ $# -eq 1 ] || usage
[[ $count =~ ^[0-9]+$ ]] || { echo "count must be a number" >&2; exit 2; }
```

Runs (checked): `opts.sh -n 3 -v data.txt` → `file=data.txt count=3 verbose=1`; `-n x` → `count must be a number`, exit 2; no arguments → usage, exit 2. Conventions: errors and usage to **stderr**, exit **2** for misuse, `1` for operational failure, `0` for success; validate before acting.

## Locking and idempotence

- **Only one instance:** `mkdir` is atomic, so `mkdir "$lock"` succeeds for exactly one caller (run: first `mkdir lock.d` → `got lock`; the second → `mkdir: lock.d: File exists`). Remove it in the EXIT trap. On Linux, `flock -n /run/lock/job.lock cmd` is simpler and releases on process death (Level 2 · 09; macOS lacks `flock`). Plain "check for a PID file" has races.
- **Idempotent actions:** running the script twice must equal running it once. Run: `grep -qxF 'setting=1' cfg || echo 'setting=1' >> cfg`, executed twice, left **1 line** in the file. Use "ensure" patterns (`mkdir -p`, `ln -sfn`, check-then-append, `install`), not blind appends. This property is what lets cron retries and re-deploys be safe (Lesson 03).
- **Atomic file replacement:** write to a temp file in the same directory and `mv` over the target; readers see the old or the new file, never half of one (Level 3 · 05).

## Other habits

- `#!/usr/bin/env bash` for portability across installs; `#!/bin/sh` only for POSIX-only scripts (test with `dash`).
- Log with timestamps to stderr or the journal (`logger -t myscript`), including *what failed and why*.
- Avoid parsing `ls`; use globs and `find -print0` (Level 1 · 03). Use `printf` instead of `echo` for portable output (Level 1 · 09).
- Use `readonly` and uppercase for constants, lowercase for locals; avoid globals in functions (`local`).
- Run `shellcheck script.sh` (not installed here, so unverified in this course) and `bash -n script.sh` (syntax check); keep scripts small, and move anything with data structures or retries into a real language (Python).
- Test scripts: run them in a temp directory with fixtures (as in Level 1's audit project), or use `bats`.
- Never `curl ... | sudo bash` from a source you don't trust, and pin versions/checksums for downloaded artifacts.

## How It Actually Works

The shell runs each command by forking and exec'ing it, then reading its exit status; `-e` just makes the shell check that status after each *simple command* and call `exit` if it's non-zero, except in the contexts the standard says are tested (conditions, `&&`/`||` left sides, negations). That is why the function inside an `&&` list ran past its `false`: the shell had already entered a "tested" context
when it called the function, and the exemption applies to everything beneath it. `local v=$(cmd)` is two things: command substitution, then the `local` builtin, whose own (successful) status becomes the statement's status. `trap ... EXIT` registers a handler the shell runs as it terminates; signals can run others (`TERM`, `INT`). Quoting controls whether the shell's word-splitting
and globbing phases apply to an expansion's result.

## Common mistakes

- **Trusting `set -e` inside functions** called from conditions.
- **`local x=$(cmd)`** and **`export X=$(cmd)`**, which hide failures.
- **Unquoted variables and `ls` parsing.**
- **No guard on empty variables in `rm -rf`.**
- **Fixed temp file names**, no cleanup trap.
- **Assuming bash 5 features on macOS's bash 3.2** (or `sh` scripts using bashisms).
- **Non-idempotent scripts** scheduled under cron.
- **Silent failure:** no logging, exit 0 after an error.

## Exercise

1. Write a deploy script skeleton with strict mode, a trap, a lock, argument validation and one idempotent step. Run it twice and from a read-only directory.
2. Reproduce the three `set -e` surprises, then rewrite the function so each failure is handled explicitly.
3. Run the same script under `dash` (`sh script.sh`) and bash 3.2/5 and list every difference you find.
4. Run `shellcheck` on your scripts from Levels 1 and 2 and fix its findings.
