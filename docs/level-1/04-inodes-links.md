---
description: "What an inode actually stores, how a directory is just a name-to-inode lookup table, and the real difference between hard links and symlinks."
---

# 04 · Files, Inodes & Links: How Linux Actually Stores Data

"A file is stored in a folder" is the mental model most people carry from other operating systems, and it's close
enough for daily use but wrong in a way that makes hard links, `rm` while a program is still reading a file, and
`df` vs `du` disagreements all look like bugs instead of the direct, predictable consequences of how Linux
filesystems actually work.

## What's really there: inodes and directory entries

Every file and directory on a filesystem like ext4 or xfs is represented by an **inode** — a fixed-size on-disk
structure holding the file's metadata: owner (UID/GID), permission bits, size, timestamps, and pointers to the data
blocks that actually hold the file's content. Critically, the inode does **not** store the filename. The filename
lives in a **directory entry** — an entry in the *parent directory's* data, which is itself just a list of
(filename, inode number) pairs. A directory is a special kind of file whose content is this list; `ls` reads that
list and, for each name, looks up the corresponding inode to show you size, permissions, and so on.

This separation is the whole reason the rest of this lesson works the way it does.

## Worked example: watching inode numbers and link counts

```text
$ echo "hello" > original.txt
$ ls -i original.txt
135 original.txt

$ ln original.txt hardlink.txt
$ ls -i original.txt hardlink.txt
135 hardlink.txt
135 original.txt

$ stat original.txt | grep Links
Device: 0,39	Inode: 135         Links: 2

$ ln -s original.txt symlink.txt
$ ls -i symlink.txt
136 symlink.txt

$ ls -l symlink.txt
lrwxrwxrwx 1 vinodkumarsigilipelli vinodkumarsigilipelli 12 Oct 22 23:30 symlink.txt -> original.txt

$ rm original.txt
$ cat hardlink.txt
hello
$ cat symlink.txt
cat: symlink.txt: No such file or directory
```

(Real output from this course's lab VM.) `ln original.txt hardlink.txt` (no `-s`) creates a **hard link**: a brand
new directory entry, `hardlink.txt`, pointing at the *exact same inode number* (`135`) as `original.txt`. They are
not two copies of a file — they are two names for one file, and `stat` confirms it by reporting `Links: 2`, the
inode's reference count. `ln -s` instead creates a **symlink**: a genuinely separate, tiny file (with its own
inode, `136`) whose content is just the text `original.txt` — a path for the kernel to follow. That's why deleting
`original.txt` leaves `hardlink.txt` completely intact (the inode and its data blocks are still referenced, so
nothing is freed) but breaks `symlink.txt`, which now points at a path that no longer resolves to anything.

## How It Actually Works

`rm` doesn't "delete a file" in the sense of erasing its content. What `unlink()` (the syscall `rm` makes) actually
does is remove *one directory entry* and decrement the target inode's link count by one. The data blocks, and the
inode itself, are only actually freed when that link count reaches **zero** — and even then, only if no process
still has the file **open**. This is why a classic trick works: a long-running process can hold a file open, you
can `rm` it from the filesystem's directory listing (making it invisible to `ls`), and the process keeps reading and
writing it fine, because the kernel keeps an inode alive as long as either a directory entry *or* an open file
descriptor references it. The space is only reclaimed when the last reference — of either kind — goes away; this
is also exactly why disk space sometimes doesn't free up after you delete a huge log file: a service still has it
open, and `lsof | grep deleted` is the standard way to find and fix it (restart the service, or truncate the file
in place with `: > /path/to/file`).

It also explains two real constraints people run into. Hard links can't cross filesystems (a different mounted
device has an entirely separate inode table, so an inode number from one has no meaning on another — `ln` will
refuse with "Invalid cross-device link"), while symlinks can, because a symlink is just a path string, resolved
fresh every time something follows it. And hard links can't point at directories (in practice; `.` and `..` are the
only hard links the kernel itself makes for you) because allowing arbitrary directory hard links would make it
possible to build a directory tree that contains itself, which breaks the basic recursive assumption nearly every
tool relies on when walking the filesystem.

## Common mistakes

- **Assuming `cp` preserves hard links.** Plain `cp` of two hard-linked files produces two independent copies with
  separate inodes; `cp -a` (or `--preserve=links` with GNU `cp`'s `-l`-aware mode) is what you need to keep them
  linked, which matters for backup tools where double-counting hard-linked data can silently inflate size estimates.
- **Deleting a symlink's target and being surprised the symlink "still exists."** `ls -l` on a broken symlink will
  still show an entry (often highlighted in red by default shell colors) — the symlink file itself is fine; it's
  only *resolving* the link (opening, `cat`-ing, `cd`-ing into it) that fails.
- **Expecting `du` and `df` to agree after deleting a large file a process still holds open.** `df` reports space
  as the kernel sees it (still allocated, because the inode's link count or open-file reference hasn't hit zero);
  `du`, which walks the *visible* directory tree, won't even see the deleted file anymore. The size discrepancy is
  real and is the single most common "where did my disk space go" support ticket on long-running servers.

## Exercise

Create a file, note its inode number with `ls -i`, then make one hard link and one symlink to it. Delete the
*original* filename. Predict, then verify: which of the two remaining names still lets you read the content? Then
open the hard-linked file with `tail -f` in one terminal, delete it with `rm` from another, and run `df -h .`
followed by `du -sh .` in the directory — explain the numbers you see using the link-count model from this lesson.
