---
description: "Level 1 project: a portable POSIX shell audit script for accounts, permissions, setuid files and listeners, with a fixture-based test suite, run on macOS."
---

# 10 · Project — A Portable System Audit Script

You'll write a small audit tool in plain POSIX `sh` that inspects accounts, permissions, setuid files and large files, then **test it** against a fixture tree you build
yourself. It uses everything in Level 1: permissions and special bits (04), users and `passwd` format (05), `find`/`awk` pipelines (03, 06), exit codes and quoting (06, 07).

!!! note "What was run"
    The script and tests were run on **macOS** (BSD tools). The `passwd` fixture is a hand-written file in Linux `/etc/passwd` format, **not taken from a real Linux system**, which lets the account
    checks run on a Mac. The script's `ss` branch (Linux) was **not run**; the Mac used the `lsof` branch. The `find -perm` forms used are POSIX, so they should behave the same
    on Linux, but I have not verified that. See Lesson 01.

## Requirements

1. Print a header: host, OS, kernel, architecture.
2. Flag accounts other than `root` with UID 0, and system accounts (UID 1 to 999) that have a login shell.
3. Flag world-writable files, and world-writable directories **without** the sticky bit.
4. Flag setuid/setgid regular files, and files larger than a threshold.
5. Report how many TCP sockets are listening (informational).
6. Exit `0` with no findings, `1` with findings, `2` on a usage error. Be safe with odd filenames, and don't modify anything.

## audit.sh

```sh
#!/bin/sh
# audit.sh - a small, portable (POSIX sh) system audit. Usage: audit.sh [-p passwd_file] [-d dir] [-m max_mb]
# Exit status: 0 = no findings, 1 = findings, 2 = usage error.
passwd_file=/etc/passwd; scan_dir=.; max_mb=50; findings=0
while getopts "p:d:m:" opt; do
  case $opt in p) passwd_file=$OPTARG ;; d) scan_dir=$OPTARG ;; m) max_mb=$OPTARG ;; *) echo "usage: $0 [-p passwd] [-d dir] [-m max_mb]" >&2; exit 2 ;; esac
done
[ -d "$scan_dir" ] || { echo "no such directory: $scan_dir" >&2; exit 2; }
finding() { findings=$((findings + 1)); printf 'FINDING: %s\n' "$1"; }

printf 'host=%s os=%s kernel=%s arch=%s\n' "$(hostname | cut -d. -f1)" "$(uname -s)" "$(uname -r)" "$(uname -m)"

# 1. accounts with UID 0 other than root (works on files in passwd format; on macOS /etc/passwd has no real accounts)
extra=$(awk -F: '!/^#/ && NF >= 3 && $3 == 0 && $1 != "root" {print $1}' "$passwd_file")
for u in $extra; do finding "extra UID 0 account: $u"; done
# 2. empty password field / login shells for system accounts are not checkable without shadow; just report accounts with a login shell and UID < 1000
low=$(awk -F: '!/^#/ && NF >= 7 && $3 > 0 && $3 < 1000 && $7 !~ /(nologin|false)$/ {print $1}' "$passwd_file")
for u in $low; do finding "system account with a login shell: $u"; done
# 3. world-writable files and directories without the sticky bit
find "$scan_dir" -xdev -type f -perm -0002 2>/dev/null | sort | while read -r f; do printf 'FINDING: world-writable file: %s\n' "$f"; done > .ww_files.$$
find "$scan_dir" -xdev -type d -perm -0002 ! -perm -1000 2>/dev/null | sort | while read -r d; do printf 'FINDING: world-writable directory without sticky bit: %s\n' "$d"; done > .ww_dirs.$$
cat .ww_files.$$ .ww_dirs.$$; findings=$((findings + $(cat .ww_files.$$ .ww_dirs.$$ | wc -l))); rm -f .ww_files.$$ .ww_dirs.$$
# 4. setuid / setgid regular files
find "$scan_dir" -xdev -type f \( -perm -4000 -o -perm -2000 \) 2>/dev/null | sort > .sg.$$
while read -r f; do finding "setuid/setgid file: $f"; done < .sg.$$; rm -f .sg.$$
# 5. big files
find "$scan_dir" -xdev -type f -size +"${max_mb}"M 2>/dev/null | sort > .big.$$
while read -r f; do finding "file over ${max_mb} MB: $f"; done < .big.$$; rm -f .big.$$
# 6. listening TCP ports (informational; Linux ss if present, else lsof)
if command -v ss >/dev/null 2>&1; then listeners=$(ss -ltnH 2>/dev/null | awk '{print $4}' | sort -u | wc -l)
elif command -v lsof >/dev/null 2>&1; then listeners=$(lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | awk 'NR>1 {print $9}' | sort -u | wc -l)
else listeners=unknown; fi
printf 'info: listening TCP sockets: %s\n' "$(echo $listeners)"
printf 'summary: %s finding(s)\n' "$findings"
[ "$findings" -eq 0 ]
```

Design choices worth noticing: it takes the passwd file as an *argument* so it can be tested without touching the real one; it writes temporary results to files in the current directory with `$$`
(the PID) in the name and removes them; `find -xdev` stays on one filesystem; the exit status reflects findings, so cron or CI can alert on it; and quoting is consistent. Known weaknesses: it reads
filenames with `while read -r` and so mishandles names containing newlines (a safer version would use `find -print0` with a NUL-aware loop, Exercise 3), and temp files in the current directory are a toy approach (use `mktemp`).

## test_audit.sh

```sh
#!/bin/sh
# Builds a fixture tree and checks audit.sh's findings. Fixtures are hand-written (not from a real Linux system).
fail=0; here=$(cd "$(dirname "$0")" && pwd)
t=$(mktemp -d) || exit 1; cd "$t" || exit 1
mkdir -p tree/clean tree/shared tree/tmpish; chmod 755 tree tree/clean
echo data > tree/clean/ok.txt; chmod 644 tree/clean/ok.txt
echo x > tree/shared/leak.txt; chmod 666 tree/shared/leak.txt
chmod 777 tree/shared; chmod 1777 tree/tmpish
printf '#!/bin/sh\n' > tree/clean/helper; chmod 4755 tree/clean/helper
head -c 3145728 /dev/zero > tree/clean/big.bin
cat > passwd.fixture <<'P'
root:x:0:0:root:/root:/bin/bash
toor:x:0:0:backdoor:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
svc:x:105:105:service:/var/lib/svc:/bin/bash
alice:x:1001:1001:Alice:/home/alice:/bin/bash
P
check() { # name expected-substring
  if echo "$out" | grep -q -- "$2"; then echo "PASS  $1"; else echo "FAIL  $1  (missing: $2)"; fail=1; fi; }
out=$(sh "$here/audit.sh" -p passwd.fixture -d tree -m 2); rc=$?
check "extra uid0 account found"         "extra UID 0 account: toor"
check "system account with login shell"  "system account with a login shell: svc"
echo "$out" | grep -q "FINDING.*daemon" && { echo "FAIL  nologin daemon flagged"; fail=1; } || echo "PASS  nologin daemon account not flagged"
check "world-writable file found"        "world-writable file: tree/shared/leak.txt"
check "world-writable dir w/o sticky"    "directory without sticky bit: tree/shared"
echo "$out" | grep -q "tmpish" && { echo "FAIL  sticky dir wrongly flagged"; fail=1; } || echo "PASS  sticky world-writable dir not flagged"
check "setuid file found"                "setuid/setgid file: tree/clean/helper"
check "big file found (>2 MB)"           "file over 2 MB: tree/clean/big.bin"
[ "$rc" -eq 1 ] && echo "PASS  exit status 1 with findings" || { echo "FAIL  exit status was $rc"; fail=1; }
mkdir clean2; echo ok > clean2/a; chmod 644 clean2/a; printf 'root:x:0:0::/root:/bin/sh\n' > p2
out=$(sh "$here/audit.sh" -p p2 -d clean2); rc=$?
[ "$rc" -eq 0 ] && echo "PASS  exit status 0 on a clean tree" || { echo "FAIL  clean tree rc=$rc"; echo "$out"; fail=1; }
sh "$here/audit.sh" -d /nonexistent 2>/dev/null; [ $? -eq 2 ] && echo "PASS  exit 2 on bad directory" || { echo "FAIL  bad dir"; fail=1; }
echo "-- full report for the fixture:"; echo "$out" >/dev/null; sh "$here/audit.sh" -p passwd.fixture -d tree -m 2
cd /; rm -rf "$t"; exit $fail
```

The test builds a fixture tree: a normal file, a `666` file inside a `777` directory, a sticky `1777` directory that must **not** be flagged, a `4755` file, and a 3 MB file, plus a fixture passwd file with
a second UID 0 account, a nologin daemon and a system account with a bash shell.

## Output

Running `sh test_audit.sh`:

```text
PASS  extra uid0 account found
PASS  system account with login shell
PASS  nologin daemon account not flagged
PASS  world-writable file found
PASS  world-writable dir w/o sticky
PASS  sticky world-writable dir not flagged
PASS  setuid file found
PASS  big file found (>2 MB)
PASS  exit status 1 with findings
PASS  exit status 0 on a clean tree
PASS  exit 2 on bad directory
-- full report for the fixture:
host=<hostname> os=Darwin kernel=27.0.0 arch=arm64
FINDING: extra UID 0 account: toor
FINDING: system account with a login shell: svc
FINDING: world-writable file: tree/shared/leak.txt
FINDING: world-writable directory without sticky bit: tree/shared
FINDING: setuid/setgid file: tree/clean/helper
FINDING: file over 2 MB: tree/clean/big.bin
info: listening TCP sockets: 9
summary: 6 finding(s)
```

All eleven checks passed, and the test script exits `0`. (The first version of my test had a mistake: the "does not flag nologin daemon" check asserted the word `daemon`
*was* present, so it reported a FAIL for correct behaviour. A test can be wrong too; read failing tests as carefully as failing code.) The "9 listening sockets" is whatever the Mac was doing at the time and is not meaningful.

Run against the real Mac `/etc/passwd` and the project folder, the script reported accounts such as `_uucp` and `_mbsetupuser` as "system account with a login shell" (they have shells in that file; it's macOS's own convention, not a Linux
finding), which is a useful reminder that audit rules encode assumptions about one platform.

## What the project teaches

1. **Testability comes from parameters**: injecting the passwd path and scan directory made the tool testable.
2. **Fixtures need negative cases**: the sticky directory and the nologin daemon exist to prove the script does *not* over-report.
3. **Exit codes are an interface.**
4. **Portability is a decision**: POSIX `find -perm -0002` and `-perm -1000` work on both BSD and GNU, while `-printf` would have been GNU-only, and `ss` needs a fallback.

## How It Actually Works

`find -perm -0002` matches files whose mode has *at least* those bits set (`-perm mode` without a sign means exactly, with `-` prefix means all of these bits, with `/` any of them in GNU).
`! -perm -1000` negates the sticky test, so `1777` directories are excluded. `-xdev` makes find skip other mounted filesystems, avoiding network mounts and `/proc`. The script's `while read -r` loops run
in subshells when fed by a pipe, so variable changes inside them are lost; that is why the findings counter is updated by counting lines from temp files and by `finding()` calls outside a pipe: a classic shell
gotcha that Lesson 07's note on subshells explains.

## Extensions

- Make it output JSON or exit codes by severity.
- Add checks for `~/.ssh` permissions (Level 2 · 08 explains the `700`/`600` expectations) and for `authorized_keys` writable by others.
- Replace temp files with `mktemp`, and use `find -print0` loops.
- On Linux, add a check that `/etc/shadow` is `0640 root:shadow` or stricter, and test it with a fixture.

## Common mistakes

- **Testing only the positive cases**, so the script flags everything and "passes".
- **Reading `passwd` from the real system in tests.**
- **Variables set inside a piped `while` loop** used after the loop.
- **Parsing `ls`** instead of using `find`.
- **GNU-only flags** (`find -printf`, `grep -P`) in a script meant to be portable.
- **Auditing as a normal user** and silently skipping unreadable directories (the script hides `find` errors with `2>/dev/null`; a real audit should report that it couldn't read something).

## Exercise

1. Run the tests, then break one rule in `audit.sh` on purpose (for example, drop the `! -perm -1000` test) and confirm the suite catches it.
2. Add a check for world-writable *parents*: any directory in the scan whose own mode is `777` without sticky. Write the failing test first.
3. Rewrite the file loops using `find -print0` and a NUL-safe reader (bash `read -d ''`), and add a fixture file with a space and one with a newline in its name.
4. On Linux, run it against `/usr` and `/etc` and triage every finding as expected or not.
