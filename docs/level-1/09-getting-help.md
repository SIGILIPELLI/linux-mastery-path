---
description: "Finding answers on the machine: man sections, reading synopses, --help, builtins vs binaries, and learning by small experiments."
---

# 09 · Getting Help: man, info & Reading Docs

The most valuable Linux skill is finding the authoritative answer on the machine in front of you, because that machine's version of a tool is the one you are actually running. The
documentation is installed alongside the software.

!!! note "What was run"
    `man`, `--help` and `apropos` were tried on **macOS**; the man-page system is the same idea on Linux, but the pages themselves differ (BSD vs GNU), which is an important
    lesson in itself. Linux-specific pages are cited from the Linux man-pages project (man7.org). See Lesson 01.

## man pages and sections

```bash
man ls              # the page for ls
man 5 passwd        # section 5 (file formats): the /etc/passwd file, not the passwd command
man -k copy         # search page descriptions (same as apropos copy)
man 7 signal        # an overview page
```

Manual **sections**:

| Section | Contents | Example |
|---|---|---|
| 1 | User commands | `ls(1)` |
| 2 | System calls | `open(2)` |
| 3 | C library functions | `printf(3)` |
| 4 | Devices / special files | `null(4)` |
| 5 | File formats and configs | `fstab(5)`, `sudoers(5)` |
| 6 | Games | |
| 7 | Overviews, conventions | `signal(7)`, `hier(7)`, `capabilities(7)` |
| 8 | System administration commands | `mount(8)`, `iptables(8)` |

Names like `passwd(1)` vs `passwd(5)` cite the section. Inside `man` (a pager): `/word` searches, `n` next match, `q` quits, `g`/`G` top and bottom. The structure is regular: NAME, SYNOPSIS,
DESCRIPTION, OPTIONS, EXIT STATUS, ENVIRONMENT, FILES, EXAMPLES, SEE ALSO. **Read SEE ALSO and EXIT STATUS**: they answer questions people spend hours on.

## Reading a SYNOPSIS

```text
ls [OPTION]... [FILE]...
grep [OPTIONS] PATTERN [FILE...]
rsync [OPTION...] SRC... [DEST]
```

`[ ]` optional; `...` repeatable; `|` alternatives; bold text literal; italic or capitalised words are names you replace. A single dash introduces short options which may be combined (`-lah`); two
dashes introduce long ones (`--all`); a bare `--` ends option parsing, so `rm -- -weird-file` works.

## Quick help from the command itself

```bash
cmd --help          # most GNU tools; short usage summary
cmd -h              # sometimes
help cd             # bash builtins have no man page; use help
type -a echo        # which echo(s) will run: builtin, alias, or file? (try it)
```

`type`/`command -v` tell you what a name resolves to. On the Mac (run), `type -a echo` printed `echo is a shell builtin` and `echo is /bin/echo`, and the two really differ: bash's builtin `echo -e "a\tb"` printed `a<TAB>b`, while `/bin/echo -e "a\tb"` printed `-e a\tb`.
Builtins can behave differently from the external program with the same name. Test with what you will actually use in the script (and prefer `printf`).

## Beyond man

- **`info`** — GNU's hyperlinked manuals (`info coreutils`), more detailed than man pages for GNU tools.
- **`/usr/share/doc/<package>/`** — READMEs, changelogs, example configs shipped by the package (Lesson 08's `dpkg -L pkg | grep doc`).
- **`apropos` / `man -k`** needs the man database built (`mandb` on Linux); if it returns nothing on a fresh container, that is why.
- **`tldr`** and cheat-sheet tools are handy but not authoritative; verify with man.
- **`--version`** : confirm which implementation you have. On the Mac, `sed --version` fails (BSD sed has no such option), which immediately tells you it's not GNU sed (run in Lesson 06).
- **Distribution documentation**: Debian's and Fedora's wikis, the Arch Wiki (excellent even for non-Arch users).
- **Kernel documentation** (`Documentation/` in the kernel tree, docs.kernel.org) for `/proc`, `/sys`, sysctls and cgroups.
- **Source**: when docs are unclear, read the code or run `strace` (Level 3 · 01) to see what the program does.

## Learning by experiment

Man pages tell you what's *supposed* to happen; experiments tell you what *does*. The habit used throughout this course: state a prediction, run a tiny test in a temp directory, compare. Examples: `touch x; chmod 4755 x; ls -l x` (Lesson 04);
`printf 'b\na\nb\n' | uniq` (Lesson 06). Do dangerous experiments in a throwaway VM or container, never on a server you care about. When something fails, read the **exact error message**: it usually names the file, the permission or the
syscall (`Permission denied` vs `No such file or directory` vs `Operation not permitted` mean different things; the last is typically a capability/ownership/immutable-flag problem rather than a mode problem).

## How It Actually Works

`man` finds a page by searching the directories in `MANPATH` (typically `/usr/share/man/man1` ... `man8`) for `name.section` files, which are text in the troff/mdoc markup, often compressed
(`ls.1.gz`). It formats them with a renderer (`groff`/`mandoc`) and displays them through a pager (`less`). The `apropos` database is a prebuilt index of NAME lines, which is why newly installed pages
don't appear until the index is rebuilt. Package managers install pages as part of each package, so the man page always matches the installed version, unlike a web search that may describe a different version.

## Common mistakes

- **Reading a web answer written for another distribution or the BSD/GNU variant** and pasting it onto your system.
- **Ignoring the section** (`man passwd` shows the command, not the file format).
- **Not reading EXIT STATUS and SEE ALSO.**
- **Assuming a shell builtin and the external command of the same name behave identically.**
- **Running destructive experiments on production.**
- **Never checking `--version`** when behaviour differs from the docs.

## Exercise

1. Find, using only on-machine documentation, which option of `ls` sorts by modification time, newest last, and test it.
2. Look up the exit status table in `man grep` (or `grep --help`) and write a script that distinguishes "no match" from "error".
3. Use `man -k signal` and `man 7 signal`. List the signals that cannot be caught and the page you used.
4. On Linux, read `man 7 hier` and `man 5 fstab`, and use them to explain the six fields of one line from your `/etc/fstab`.
