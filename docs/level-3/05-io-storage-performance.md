---
description: "The Linux I/O path: page cache, write-back, fsync, the block layer, reading iostat, plus an honest macOS write/read experiment."
---

# 05 · I/O, the Block Layer & Storage Performance

Storage is the slowest part of most systems, and the Linux I/O path has several layers that hide that fact, until they don't. This lesson follows a write from `write()` to the disk and shows which `iostat` columns reveal a struggling device.

!!! note "What was run"
    `iostat`, `/sys/block/*/queue`, and the dirty-page sysctls are Linux interfaces and **were not run**; they are described from `iostat(1)` (man7.org) and the kernel's `vm.rst` sysctl documentation (docs.kernel.org, October 2026). I ran a **write/fsync/read experiment on macOS (APFS on an SSD)** whose results are macOS-specific and partly
    inconclusive, as explained below. See Level 1 · Lesson 01.

## The path of a write

```text
application write()  →  page cache (dirty pages in RAM)   ← write() returns here
        ↓ (later, by flusher threads, or immediately on fsync)
filesystem (ext4/XFS: allocation, journal)  →  block layer (queues, I/O scheduler)  →  device driver  →  disk (and its own cache)
```

1. `write()` copies data into the **page cache** and marks pages **dirty**; the call returns quickly. Your data is *not yet on disk*.
2. Kernel flusher threads write dirty pages back later. Per the kernel docs: `vm.dirty_background_ratio` is the percentage of available memory at which background writeback starts; `vm.dirty_ratio` is the point at which **the writing process itself is forced to write** (the stalls you feel); `dirty_expire_centisecs` defines how old
   dirty data must be to be written; `dirty_writeback_centisecs` is how often the flushers wake. (Typical defaults are 10% and 20%, but I did not verify those numbers in this session; check `sysctl vm.dirty_ratio`.)
3. `fsync(fd)` forces that file's dirty data (and metadata) to storage and returns when the device reports completion: this is what a database calls at commit.
4. The device may have its own volatile cache; reliable devices honour flush/FUA commands. Cheap drives lying about flushes are why power-loss tests exist.

### What I measured on macOS

```text
buffered write of 256 MB returned after 215 ms (1,246 MB/s apparent); fsync then took 5 ms; F_FULLFSYNC 43 ms
read with cache  : 12,302 MB/s ; again: 12,094 MB/s
read with F_NOCACHE (bypass cache): 13,434 MB/s ; again: 13,912 MB/s
```

- The write "finished" in 215 ms at an apparent 1.2 GB/s, then `fsync` took only 5 ms: **most of the data had already been flushed in the background** (write-behind), or this fast NVMe drive absorbs writes quickly. Either way, the application saw acknowledgement long before the data was durable.
- On macOS, plain `fsync` does not force the drive to flush its own cache; `F_FULLFSYNC` does (43 ms here). The distinction is macOS-specific; on Linux `fsync` is expected to flush the device cache when barriers are enabled.
- **My attempt to show the page cache's effect failed.** Reads were already 12 to 14 GB/s, and `F_NOCACHE` did not slow them down; the data was probably still cached or the flag doesn't work the way I assumed on this filesystem. I cannot claim a measured cache/no-cache ratio. On Linux the usual way to take the cache out is `echo 3 > /proc/sys/vm/drop_caches` (root, test
  machines only) or `O_DIRECT`; I did not run either.

## Durability: what each call guarantees

| Call | Guarantee |
|---|---|
| `write()` | Data copied to the kernel; may be lost on power failure |
| `fsync(fd)` | File data and metadata reach stable storage (assuming honest hardware) |
| `fdatasync(fd)` | Data (and metadata required to read it) only; cheaper when only contents changed |
| `sync()` / `syncfs()` | Flush everything / one filesystem |
| `O_SYNC` / `O_DSYNC` | Every write behaves as followed by fsync / fdatasync |
| `O_DIRECT` | Bypass the page cache (aligned I/O; used by databases that manage their own cache) |
| `rename()` | Atomic replace of a name; combine with `fsync` of the file and the directory for crash-safe updates |

Crash-safe file replacement pattern: write to `file.tmp`, `fsync` it, `rename` over `file`, `fsync` the directory. Programs that skip steps work until the day power fails.

## The block layer and I/O schedulers

The block layer queues requests, merges adjacent ones, and (for spinning disks) orders them to reduce seeks. Modern kernels use the multi-queue block layer; schedulers include `none` (typically best for fast NVMe), `mq-deadline` (bounded latency), `bfq` (fairness for interactive workloads) and `kyber`. See and set per device:

```bash
cat /sys/block/nvme0n1/queue/scheduler      # [none] mq-deadline ...   (not run; the bracket marks the active one)
cat /sys/block/sda/queue/rotational         # 1 = spinning disk, 0 = SSD
cat /sys/block/sda/queue/nr_requests
```

Choosing a scheduler rarely matters as much as the queue depth you drive and the workload pattern (sequential vs random, read vs write, I/O size). Measure with `fio`, which can generate specific patterns (random 4K reads at queue depth 32, sequential 1 MB writes...) and report latency percentiles. Always test on the real filesystem and storage
class (cloud volumes have throughput and IOPS limits and burst credits, which show up as sudden plateaus).

## Reading iostat (Linux; not run)

```bash
iostat -xz 1       # extended stats, hide idle devices, every second
```

Columns, from `iostat(1)`: `r/s`, `w/s` (operations per second), `rkB/s`, `wkB/s` (throughput), `r_await`/`w_await` ("average time in milliseconds for requests ... to be served. This includes the time spent by the requests in queue and the time spent servicing them"), `aqu-sz` ("the average queue length of the requests that were issued to the device"),
and `%util`. The man page warns about `%util`: it is the share of time the device had requests in flight; "device saturation occurs when this value is close to 100% for devices serving requests serially. But for devices serving requests in parallel, such as RAID arrays and modern SSDs, this number does not reflect their performance limits."

So interpret like this:

| Pattern | Likely story |
|---|---|
| High `await`, high `aqu-sz`, high `%util` on a single HDD | Saturated device: reduce load, spread I/O, faster disk |
| High `await` with low `r/s + w/s` | Device or network volume is slow per request (failing disk, throttled cloud volume, noisy neighbour) |
| High `%util` on NVMe but `await` stays low | Not necessarily a problem: parallel device; look at latency, not util |
| High `w_await` right after bursts | Dirty-page flush storms; check `dirty_*` settings and `fsync` frequency |
| High `wa` in `top`/`vmstat` plus D-state processes | Processes are blocked on storage (Lesson 04) |

A latency-oriented rule: users feel **latency**, so watch `await` percentiles from the application side too; averages hide the tail.

## Other effects worth knowing

- **Writeback stalls**: when dirty pages hit `dirty_ratio`, writers block, and a latency-sensitive service can freeze for seconds. Lower `dirty_background_ratio` to start flushing earlier, or use `dirty_bytes` for large-RAM machines.
- **Filesystem journaling modes** trade metadata vs data ordering for speed and safety (ext4 `data=ordered` default).
- **Read-ahead** prefetches sequential reads (`blockdev --getra`); great for scans, wasteful for random access.
- **Mount options**: `noatime` removes a write per read; `discard` vs periodic `fstrim` for SSDs.
- **NFS/network storage**: latency and the "hung mount" problem (processes stuck in D state, Level 1 · 07); `soft` vs `hard` mount semantics trade data safety for hangs.
- **Cloud volumes**: IOPS/throughput caps and burst credits mean a benchmark at noon proves nothing at 3 a.m.

## How It Actually Works

The page cache is organised per file (and offset): reading a file first checks the cache, and misses trigger a disk read plus read-ahead. Writes dirty the cached page; a `bdi` (backing device info) tracks dirty counters per device, and flusher threads (`kworker/flush-*`) pick inodes with old dirty pages and issue write requests, in batches the
block layer sorts and merges. `fsync` walks the file's dirty pages, submits them, waits for completion, then (for journaled filesystems) commits the journal transaction with a flush so metadata is consistent after a crash. Because both reading and writing go through the cache, a lot of "disk" performance is really memory performance
until the working set exceeds RAM, at which point the numbers fall off a cliff (Lesson 02).

## Common mistakes

- **Believing `write()` means saved.**
- **Benchmarking a cached file** and calling it disk speed (or the reverse). I nearly did this myself above.
- **Reading `%util` on SSD/NVMe as a saturation gauge.**
- **Using `dd` as a database benchmark** (sequential, cached, wrong shape); use `fio` with realistic patterns.
- **Ignoring cloud volume limits and burst credits.**
- **`fsync` on every tiny write** in a hot path without batching (group commit).
- **Dropping the page cache on production to "fix" performance.**

## Exercise

1. On a Linux VM, install `fio` and compare random 4K reads vs sequential 1M reads on the same file, with and without dropping caches (VM only); record IOPS, throughput and p99 latency.
2. Write a program that appends 10,000 small records with (a) no fsync, (b) fsync per record, (c) fsync every 100 records; compare time and state the durability you give up in (c).
3. Run `iostat -xz 1` while `dd if=/dev/zero of=big bs=1M count=2000 oflag=direct` runs; match each column to what you expect.
4. Implement the crash-safe replace pattern (tmp, fsync, rename, fsync dir) in a language you know.
