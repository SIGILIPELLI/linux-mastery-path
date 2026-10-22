---
description: "Inodes, hard vs symbolic links, what rm really does, find, and quoting traps, demonstrated on macOS with notes on Linux differences."
---

# 03 · Files, Directories, Links & Inodes

A filename is not the file. On Unix filesystems a file is an **inode**: a record holding its type, owner, permissions, size, timestamps and where its data blocks are. A directory is
a table mapping names to inode numbers. Once you hold that picture, hard links, symbolic links, "deleted but still using disk space", and
`mv` being instant all make sense.

!!! note "What was run"
    The link and `find` experiments below were **run on macOS (Darwin, APFS, BSD userland)** in a temporary directory; `stat` and
    `ls` flags differ from GNU/Linux (I note where). The inode concepts are the same on Linux ext4/XFS. Linux-only commands are
    marked not run (Lesson 01).

## Inodes and directory entries

```bash
echo hello > a.txt
ln a.txt hard.txt          # hard link: another name for the same inode
ln -s a.txt soft.txt       # symbolic link: a tiny file containing the path "a.txt"
ls -li a.txt hard.txt soft.txt
```

Output on macOS (inode number, permissions, link count, name):

```text
100330426 -rw-r--r--  2  a.txt
100330426 -rw-r--r--  2  hard.txt
100330429 lrwxr-xr-x  1  soft.txt
```

- `a.txt` and `hard.txt` have the **same inode number** (100330426) and a **link count of 2**: two directory entries, one file.
  Neither is the "original".
- `soft.txt` has its **own inode** (100330429) and is type `l`; it merely stores the text `a.txt`.
- (A trailing `@` in `ls -l` output on macOS marks extended attributes. Linux doesn't print that.)

GNU/Linux `stat` uses `stat -c '%i %h %n' files`; the BSD `stat` on the Mac needed `stat -f '%i %l %N' files` and printed
`100330426 2 a.txt`, `100330426 2 hard.txt`, `100330429 1 soft.txt`. Same data, different flags: a script for both must handle each form.

### What `rm` really does

After `rm a.txt`:

```text
cat hard.txt   ->  hello                         # the data survived: the inode still has a link
cat soft.txt   ->  cat: soft.txt: No such file or directory    # the symlink's target name is gone: a "dangling" link
```

`rm` doesn't erase data. It **removes a directory entry** (`unlink`) and decrements the inode's link count. Only when the count reaches
zero *and* no process still has the file open does the kernel free the inode and blocks. That has two operational consequences:

1. **Deleted-but-open files keep using disk space.** If a process holds a 10 GB log open and you `rm` it, `df` still shows the space used until the
   process closes it or exits. On Linux, `lsof +L1` lists open files with a link count below one, and the file is reachable through
   `/proc/<pid>/fd/<n>` (not run here). Truncating a live log (`: > file`) frees the space without removing the open file.
2. **`mv` within a filesystem is instant** because it only edits directory entries. Moving across filesystems must copy the data and delete the original.

### Hard vs symbolic links

| | Hard link | Symbolic link |
|---|---|---|
| What it is | Another name for the same inode | A file containing a path |
| Crosses filesystems | No | Yes |
| Can link directories | No (normally) | Yes |
| If the target is deleted | Data survives | Link dangles |
| Shows in `ls -l` as | Ordinary file, link count > 1 | `l`, with `-> target` |

Use symlinks for most things (`/etc/alternatives`, `current -> releases/42` deploy switching, Level 4). Relative symlinks resolve relative
to the link's directory, a frequent source of "works from here, breaks from there".

## Finding files

`find` walks a directory tree and tests each entry:

```bash
mkdir -p t/a t/b; touch t/a/x.log t/b/y.log t/b/z.txt
find t -name '*.log'                      # t/a/x.log  t/b/y.log   (run)
find t -name '*.log' -exec echo found {} \;     # runs a command per match; prints "found t/a/x.log" ...  (run)
find t -type f -mtime +7                  # files modified more than 7 days ago
find /var/log -type f -size +100M         # large files (GNU and BSD both accept this form)
find . -type f -print0 | xargs -0 wc -l   # safe with spaces: NUL-separated
```

Quote the pattern (`'*.log'`) so the shell doesn't expand it first. `-exec cmd {} +` batches many files into one command, which is much faster than `\;`.
`find ... -delete` removes matches; always run the `find` without `-delete` first.

## Quoting: spaces in filenames

```bash
f="a b.txt"; touch "$f"
ls $f        # run:  ls: a: No such file or directory   ls: b.txt: No such file or directory
ls "$f"      # run:  a b.txt
```

Unquoted `$f` is split on whitespace into two arguments. **Always quote variable expansions** (`"$f"`, `"$@"`) unless you want word splitting. Filenames
may legally contain spaces, newlines, quotes and leading dashes; the robust idioms are `--` to end options (`rm -- "$f"`), NUL-separated
lists (`-print0`, `xargs -0`), and shell globs (`for f in ./*`) instead of parsing `ls` output.

## Timestamps

Each inode records three times: **mtime** (content modified), **ctime** (inode changed: permissions, owner, link count), **atime** (last read; many systems reduce its updates
with `relatime`). There is **no creation time** guaranteed by POSIX, and `ctime` is not "creation time", a common
misunderstanding. `touch -d` sets times on GNU; BSD uses `touch -t`.

## How It Actually Works

A directory is a file whose content is a list of (name, inode number) pairs. Looking up `hard.txt` finds inode 100330426 and the kernel loads
that inode; a second name pointing to the same number gives the same inode. Inode numbers are unique **per filesystem**, so hard links can't cross
them. A symbolic link's inode stores the target path as its data (short paths are stored inside the inode itself on some filesystems), and the kernel
re-resolves the path text each time it follows the link, which is why it can dangle. The link count and the "open file" reference count are both
tracked; the data blocks are released when both reach zero. Filesystems also have a finite number of inodes: a disk can report plenty of
free space and still fail with "No space left on device" if the inodes are exhausted (millions of tiny files); `df -i` shows inode usage
(Linux and macOS; not run here).

## Common mistakes

- **Thinking `rm` frees space immediately** while a process still has the file open.
- **Unquoted variables** that split on spaces or glob-expand.
- **Parsing `ls` output** in scripts.
- **`find ... -exec rm {} \;` without a trial run**, or a pattern that matches more than intended.
- **Relative symlinks** created from the wrong directory.
- **Assuming `ctime` is creation time.**
- **Hard-link surprises**: editing through one name changes "all copies", because there is only one file; some editors replace the file and break the link.

## Exercise

1. Reproduce the link experiment. Edit the file through `hard.txt` and read through the other name; then use an editor that replaces files
   (or `sed -i`) and check whether the link count and inode change on your system. Explain what you saw.
2. Create a filename with a space and one starting with `-`. Delete both safely.
3. Write a `find` command that lists regular files larger than 1 MB, not modified in 30 days, under a directory, null-separated into `xargs -0 ls -lh`.
4. On Linux, create a 100 MB file, open it with `tail -f` in another terminal, delete it, and use `df` and `lsof` to see the space still used. Then free it.
