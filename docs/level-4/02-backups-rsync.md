---
description: "Backups that restore: 3-2-1, tar and rsync tested on macOS, the rsync size-and-mtime trap, --link-dest snapshots, checksums and restore drills."
---

# 02 · Backups: tar, rsync & Restore Testing

A backup you have never restored is a hope, not a backup. This lesson covers the basic Linux tools, the design questions that matter more than the tools, and some behaviours of `rsync` that I tested and that surprised me.

!!! note "What was run"
    All `tar`, `rsync` and checksum runs were on **macOS**, using the system's `bsdtar` 3.5.3 and **`openrsync`** (protocol 29, Apple's rsync-compatible implementation, not GNU rsync). Behaviour I observed may differ from GNU rsync 3.x on Linux in edge cases and options; I note the portable lessons. Snapshot/LVM/database-dump commands were not run. See Level 1 · Lesson 01.

## Design first

| Question | Why it matters |
|---|---|
| **RPO**: how much data can you afford to lose? | Sets backup frequency (nightly = up to a day lost) |
| **RTO**: how long can restoration take? | Sets technology (full restore of 5 TB over a network may take a day) |
| **What exactly** needs backing up? | Data, configuration (`/etc`), databases (consistent dumps/snapshots), secrets (separately, carefully), *not* caches or rebuildable software |
| **Where?** | **3-2-1**: at least 3 copies, on 2 different media/systems, 1 off-site (or in another account/region). RAID and replication are not backups (Level 2 · 05) |
| **Who can delete them?** | If an attacker or a bug on the server can delete the backups, they're not safe: use append-only/immutable storage or pull-based backups from a separate host |
| **Is it encrypted?** | Backups contain everything; encrypt at rest and in transit, and keep the keys separately |
| **Has it been restored?** | Schedule restore drills |

## tar: archive with metadata

```bash
tar -C src -czf backup.tar.gz .       # create (c), gzip (z), file (f), relative to src
tar -tzf backup.tar.gz | head         # list
tar -C restore -xzf backup.tar.gz     # extract
```

Run: the listing showed `./`, `./a/`, `./a/f1.bin`, `./a/link`, `./b/app.conf` (relative paths are good practice; absolute paths in archives are dangerous to extract). After extracting into a new directory, `app.conf` still had mode `-rw-------` and the symlink `a/link` still pointed at `../b/app.conf`, so permissions and symlinks are preserved.
When restoring as root, add `--same-owner`/`-p` to keep ownership and permissions (GNU tar's default for root is to preserve; bsdtar's differs, so state it), and use `--acls --xattrs` (GNU) if you rely on ACLs (Level 1 · 04). Test integrity: `gzip -t file.gz` and `tar -tzf`: a **truncated** archive (I cut mine to 5,000 bytes) made `gzip -t` print `unexpected end of file` and `tar -tzf` exit 1.
Do both after every backup.

## rsync: efficient copies

```bash
rsync -a src/ dst/                 # -a = recursive + preserve perms, times, symlinks, owner, group
rsync -a --delete src/ dst/        # also delete files in dst that are gone from src
rsync -aHAX --numeric-ids src/ host:/backup/   # preserve hard links, ACLs, xattrs, numeric IDs (GNU rsync flags)
```

Findings from my runs (openrsync):

1. **A second run transferred nothing**: `Number of files transferred: 0` (8 files in the tree, 300,023 bytes total). rsync compares size and modification time first and copies only what differs.
2. **`--delete` mirrors deletions, including accidents.** I removed `f3.bin` from the source: plain `rsync -a` left it in the destination (`f1.bin f2.bin f3.bin link`); with `--delete` it was removed (`f1.bin f2.bin link`). A mirror is not a backup: delete a file by mistake, sync, and the backup is gone too. Use snapshots (below) or keep deleted files (`--backup --backup-dir`).
3. **Trailing slash matters.** `rsync -a src dst2/` created `dst2/src/...` (listing: `src`), while `rsync -a src/ dst3/` copied the *contents* (`a b`). Forgetting the slash with `--delete` can delete a lot of the wrong thing; do a `--dry-run` (`-n`) first.

### The size-and-mtime trap (run)

rsync's "quick check" treats a file as unchanged if size and modification time match. I rewrote a 10-byte file (`config v1` → `config v2`, same length) and set its mtime equal to the old one, then ran `rsync --link-dest=snap1 src/ snap2/`:

```text
snap2 content: config v1 | same inode as snap1: yes          ← the change was NOT detected; snap2 hard-linked the old file
with --checksum: snap3 content: config v2                   ← comparing checksums found it
rewriting after a 1 s pause: snap4 content: config v3        ← a normal change (different mtime) is detected
```

(In my first, accidental version of this test, the rewrite and the original were within the same second and the same size, so the change silently didn't propagate; I reproduced it deliberately above.) Real-world versions: files modified by tools that restore old mtimes, databases and VM disk images edited in place, timestamps with coarse (1 or 2 second) resolution on some filesystems. Mitigations: `--checksum` (reads every file, slow), periodic full verification, and backing up databases via
dumps/snapshots instead of copying live files.

### Snapshot backups with --link-dest

```bash
rsync -a --link-dest=/backup/2026-10-20 /data/ /backup/2026-10-21/
```

Unchanged files become **hard links** to the previous snapshot (run: the unchanged `f1.bin` had the same inode, 100339578, in `snap1` and `snap2`); changed or new files are copied. Every snapshot looks like a complete copy and can be browsed or restored directly, yet costs only the changed data (`du` reported snap1 at 204 KB and snap2 at only 100 KB, since `du` counts a hard-linked file once per run, so
snap2 showed just its new 100 KB file). Deleting an old snapshot is safe: data blocks remain while any snapshot links to them (Level 1 · 03).
Rotate by date, keep daily/weekly/monthly sets, and delete old ones. Tools built on the same idea or better: `restic`, `borg`, `kopia` (deduplicated, encrypted, verifiable repositories), which I did not run; for most servers they're the better default than hand-rolled rsync.

## Verifying: checksums and restore drills

Create a manifest from the source and verify the restore against it:

```bash
( cd src && find . -type f -print0 | sort -z | xargs -0 shasum -a 256 ) > sums.txt     # GNU: sha256sum
( cd restore && shasum -a 256 -c ../sums.txt )
```

Run: all four files verified `OK` after extracting the tar. I then appended a line to `restore/a/f1.bin` and re-checked: `./a/f1.bin: FAILED` and `WARNING: 1 computed checksum did NOT match`. A manifest also detects silent corruption (bit rot) in long-lived backups when re-verified periodically.

A **restore drill**: on a schedule, restore a random backup to a scratch machine and run the application's health check. Record the time taken (your actual RTO) and any missing pieces (configuration files, secrets, database users, certificates). Many organisations discover only during a restore that the backup didn't include the thing that mattered.

## Consistency: files that change while you copy them

Copying a file that is being written yields a torn copy. For **databases**: use their tools (`pg_dump`/`pg_basebackup`, `mysqldump --single-transaction`, `redis-cli --rdb`; see those courses), or filesystem/LVM snapshots plus database flush hooks. For **VMs and logs**: snapshot first (LVM, Btrfs/ZFS snapshots, cloud volume snapshots) and back up the snapshot, then release it (Level 2 · 05).
`rsync` and `tar` print warnings about "file changed as we read it"; treat those warnings as failures for critical data.

## Automating safely

- Run from a timer or cron (Level 2 · 02, 09) with locking, timeout and logging to the journal; exit non-zero on failure and **alert on failure and on silence** (a missing success heartbeat).
- Use a dedicated backup user and SSH key restricted to `rsync` (`command="rsync --server ..."` in `authorized_keys`, Level 2 · 08) or pull backups from the backup host.
- Test restores of *your* backup tool regularly, including after upgrades.
- Retention: keep enough history to catch slow corruption (mistakes noticed weeks later), but delete what regulation requires deleting (privacy law and backups interact).

## How It Actually Works

rsync's classic algorithm splits a changed file into blocks, computes a cheap rolling checksum and a strong checksum per block on the receiver, and sends only the blocks the sender sees as different, which is why updating a large file with a small change is cheap over a slow link. The quick check (size + mtime) decides *which files* need that treatment at all; it is a heuristic, hence the trap above.
`--link-dest` makes the sender, for each file identical to the version in the reference directory, create a hard link instead of copying. tar writes a stream of header blocks (path, mode, owner, size, mtime) followed by data; it's a format, not a compression, which is why you pipe it through gzip/zstd, and why it can be streamed over SSH (`tar c . | ssh host 'tar x -C /dest'`).

## Common mistakes

- **Never testing a restore.**
- **`--delete` on a mirror treated as a backup**, or `--delete` with the wrong trailing slash.
- **Backing up to the same disk/server** that holds the originals.
- **Copying live database files.**
- **Forgetting configuration and secrets** (or storing secrets unencrypted in the backup).
- **Backups deletable by the system they protect.**
- **Relying on size+mtime** for data modified in place.
- **No monitoring** (the job has been failing since March).
- **Absolute paths in archives** extracted over a live system.

## Exercise

1. Reproduce the snapshot and checksum experiments; then make a "ransomware" change (modify every file) and show how an older snapshot restores the originals.
2. Write a backup script (strict mode from Lesson 01) that makes a dated `--link-dest` snapshot, verifies a sample of files against a manifest, deletes snapshots older than 14 days, and exits non-zero on any failure.
3. Do a full restore drill on a scratch VM: time it, and list everything you had to fix by hand.
4. Compare `restic` or `borg` with your rsync script for the same data: repository size, speed of the second run, and verification options.
