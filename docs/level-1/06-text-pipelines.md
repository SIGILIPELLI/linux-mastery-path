---
description: "Pipelines with grep, awk, sed, sort, uniq and xargs on a sample log, with real runs and the BSD vs GNU differences that break scripts."
---

# 06 · Text Streams, Pipes & the Core Tools

Unix tools are small programs that read text on standard input and write text on standard output, so you can connect them with `|`. Most
day-to-day Linux investigation is a pipeline: pull lines from a log, pick fields, sort, count. This lesson builds that skill on a tiny web
log and flags the places where the same command behaves differently on macOS (BSD) and Linux (GNU).

!!! note "What was run"
    Every pipeline and output in this lesson was **run on macOS (zsh/bash with BSD userland)**, on a 5-line sample access log I wrote. The
    pipelines use POSIX features, so they work on Linux; where flags differ between BSD and GNU the lesson shows the macOS result and names the GNU form. I did not run them on a GNU system.
    For the language itself, see the [Shell Mastery Path](https://sigilipelli.github.io/shell-mastery-path/).

The sample `access.log`:

```text
10.0.0.1 - - [21/Oct/2026:10:00:01] "GET /index.html" 200 512
10.0.0.2 - - [21/Oct/2026:10:00:02] "GET /api/users" 500 90
10.0.0.1 - - [21/Oct/2026:10:00:03] "POST /api/login" 200 40
10.0.0.3 - - [21/Oct/2026:10:00:04] "GET /api/users" 500 90
10.0.0.2 - - [21/Oct/2026:10:00:05] "GET /index.html" 304 0
```

## The count-and-rank idiom

```bash
awk '{print $1}' access.log | sort | uniq -c | sort -rn
```

```text
   2 10.0.0.2
   2 10.0.0.1
   1 10.0.0.3
```

Four stages: extract a field, **sort** (so identical lines are adjacent), `uniq -c` (count runs of identical adjacent lines), `sort -rn` (rank by count). `uniq` only collapses
*adjacent* duplicates, which is why `printf 'b\na\nb\n' | uniq` printed `b a b` (unchanged) while `... | sort | uniq` printed `a b`. Forgetting the first `sort` is the most common bug.

Status codes, the same way, using the **last-but-one** field (`$(NF-1)`) because the number of fields varies:

```bash
awk '{print $(NF-1)}' access.log | sort | uniq -c | sort -rn      #  2 500 / 2 200 / 1 304
```

## awk: fields, conditions, accumulators

awk reads lines, splits them into `$1 ... $NF` fields, and runs `pattern { action }` rules.

```bash
awk '{b[$(NF-1)] += $NF} END { for (s in b) print s, b[s] }' access.log | sort
# 200 552
# 304 0
# 500 180
```

That sums bytes per status code with an associative array. Careful with field numbers: my first attempt to list the paths of 5xx responses used `$7`:

```bash
awk '$(NF-1) ~ /^5/ {print $7}' access.log | sort | uniq -c       # printed "2 500", not the paths!
```

The line splits on whitespace as `10.0.0.2 | - | - | [21/Oct/...] | "GET | /api/users" | 500 | 90`, so `$6` is `/api/users"` and `$7` is the status `500`. The command printed the status
twice instead of the paths, with no error. **Print the line (`awk '...{print}'`) and count fields before you trust a field number**, or use a real log parser for formats with
quoted fields. The fix is `$6` (and `tr -d '"'` to strip the quote).

## grep

```bash
grep -c 'GET' access.log        # 4   count matching lines
grep -vc 'GET' access.log       # 1   count NON-matching lines
grep -o '/api/[a-z]*' access.log | sort -u     # /api/login  /api/users   print only the matched part
```

Exit status matters in scripts: `0` = a match, `1` = no match, `2` = error (run: `grep -q a file; echo $?` gave `0`; `grep -q zzz file` gave `1`; `grep zz nofile` gave `2`).
`set -e` scripts must treat `1` as "no match", not as failure. `-E` gives extended regular expressions (run: `echo abc123 | grep -oE '[0-9]+'` printed `123`); **`-P` (Perl regex) is a GNU extension**: on macOS it
failed with `grep: invalid option -- P`.

## sed, tr, cut, sort

```bash
sed -n '2,3p' access.log                    # print lines 2-3 only
sed 's/10\.0\.0\./HOST-/' access.log        # first line becomes: HOST-1 - - [21/Oct/...
echo "Hello World" | tr 'a-z' 'A-Z'         # HELLO WORLD
cut -d' ' -f1 access.log                    # first space-separated field
printf '10\n9\n100\n' | sort                # 10 100 9   (lexical!)
printf '10\n9\n100\n' | sort -n             # 9 10 100   (numeric)
printf '1K\n2M\n500\n' | sort -h            # 500 1K 2M  (human-readable sizes; GNU, also present here)
```

Sorting numbers without `-n` is a quiet bug. Also set `LC_ALL=C` for byte-order sorting that is fast and identical across machines.

## Portability traps (BSD vs GNU), observed

| Task | GNU/Linux | macOS (BSD), as run |
|---|---|---|
| In-place sed | `sed -i 's/a/b/' f` | That fails (the error began `sed: 2: "b.log`, because BSD sed took `s/GET/get/` as the backup suffix and `b.log` as the script); BSD needs `sed -i '' 's/a/b/' f` |
| Perl regex in grep | `grep -P '\d+'` | `grep: invalid option -- P` |
| `uniq` by prefix | `uniq -w 1` | `uniq: invalid option -- w` |
| `xargs` with empty input | runs the command once unless `-r` | `printf '' \| xargs echo ran` printed nothing: BSD skips; GNU runs it, so use `xargs -r` on GNU |
| Date arithmetic | `date -d yesterday +%F` | `date: illegal option -- d`; BSD form `date -v-1d +%F` (printed `2026-10-21`) |
| `stat` format | `stat -c '%i' f` | `stat -f '%i' f` |

Strategy for portable scripts: stick to POSIX options, or detect the flavour, or install GNU tools on the Mac (`brew install coreutils gnu-sed` gives `gsed`, `gdate`), or run scripts in a Linux container.

## Process substitution, xargs, tee, here-docs

```bash
comm -12 <(printf 'a\nb\nc\n') <(printf 'b\nc\nd\n')     # b c   lines common to two sorted inputs
printf 'a\nb\nc\n' | xargs -n1 echo item                  # item a / item b / item c
echo abc | tee t.txt | tr a-c x-z                         # writes t.txt AND passes on: xyz
n=$(wc -l < access.log); echo "lines=$((n))"              # command substitution + arithmetic: lines=5
```

`<(...)` is a bash/zsh feature, not POSIX `sh`. `xargs` turns lines into arguments; use `-0` with `find -print0` for odd filenames (Lesson 03).

## Pipeline exit status

```text
false | true; echo $?                          # 0   the status is the LAST command's
bash -c 'set -o pipefail; false | true; echo $?'   # 1   with pipefail, any failure fails the pipeline
```

Without `pipefail`, `broken_cmd | sort > out && echo done` reports success when `broken_cmd` failed. Robust scripts use `set -euo pipefail` (Level 4 · 01).

## How It Actually Works

`a | b` is implemented by the shell calling `pipe()` to get a pair of file descriptors (a kernel buffer, 64 KiB by default on Linux), then forking both
processes with `a`'s stdout wired to the pipe's write end and `b`'s stdin to the read end. **Both run at the same time**: `b` consumes while `a` produces, with
the kernel blocking a fast writer when the buffer is full and a reader when it's empty. That's why pipelines stream huge files in constant memory (until a stage such
as `sort` must see all input) and why `head` can end `yes | head` early: when `head` exits, the next write by `yes` raises SIGPIPE and kills it. Each tool's behaviour (field splitting in awk, regular
expression engines in grep/sed) is purely in userland; the kernel only moves bytes.

## Common mistakes

- **`uniq` without `sort`.**
- **Numeric data sorted lexically**, or locale-dependent sort differences between machines.
- **Wrong awk field numbers** with quoted or variable-width fields.
- **Using GNU-only flags in scripts that also run on macOS** (or BSD flags on Linux).
- **Parsing structured data (JSON, CSV with quotes) with grep/awk**; use `jq`, `csvkit` or a language.
- **Unquoted globs and variables** in pipelines.
- **Ignoring `grep`'s exit code 1** under `set -e`, or ignoring pipeline failures without `pipefail`.

## Exercise

1. Using the sample log, print the three most requested paths with counts, stripping the trailing quote.
2. Print the total bytes for requests that were not `GET`, using only awk.
3. Rewrite the in-place edit so it works on both macOS and Linux (for example by writing to a temp file and `mv`).
4. Time a 100 MB pipeline `seq 1 5000000 | awk '{s+=$1} END{print s}'` and explain why memory stays small.
