---
description: "I/O schedulers, the rotational hint, and a real virtual disk that reports itself as spinning when it almost certainly isn't."
---

# 03 · Filesystem Performance & I/O Scheduling

"The disk is slow" sometimes means the disk, and sometimes means the layer of scheduling decisions sitting
between a program's `write()` call and the physical (or virtual) device actually receiving it. This lesson looks
at that scheduling layer directly, and runs into a real, honest surprise about how virtualization can make the
kernel's own hints about hardware unreliable.

## I/O schedulers: not all storage is reordered the same way

The Linux block layer queues I/O requests and can reorder, merge, or delay them before they reach the actual
device — governed by a chosen **I/O scheduler**. `mq-deadline` (a common modern default) prioritizes fairness and
bounded latency, ensuring no request waits indefinitely. `bfq` (Budget Fair Queueing) optimizes for interactive
responsiveness on slower devices, at some cost to raw throughput. `none` disables scheduling-layer reordering
almost entirely, which is often the *right* choice for genuinely fast NVMe storage, where the device's own
internal queue and the host's many parallel hardware queues already do a better job than software reordering
could — reordering has a cost, and skipping it is correct when the device doesn't need the help.

## Worked example: a real scheduler, and a real, surprising hint

```text
$ cat /sys/block/vda/queue/scheduler
none [mq-deadline]

$ cat /sys/block/vda/queue/nr_requests
256

$ cat /sys/block/vda/queue/rotational
1

$ sudo dd if=/dev/zero of=iotest.img bs=1M count=200 oflag=direct
200+0 records in
200+0 records out
209715200 bytes (210 MB, 200 MiB) copied, 0.148003 s, 1.4 GB/s
```

(Real output from this course's lab VM.) `mq-deadline` is the active scheduler (shown in brackets, `none` also
available as an alternative). `nr_requests` (256) is the queue depth the block layer will hold before applying
backpressure to the application. The genuinely interesting line is `rotational`, which reports **`1`** — meaning
the kernel believes this is a **spinning hard disk**. It almost certainly is not: this is a `virtio_blk` device
inside a VM, backed by whatever storage the host actually uses (on this lab's Apple Silicon Mac, backed by
flash/SSD storage underneath several layers of virtualization). The `1.4 GB/s` raw write throughput in the `dd`
test is itself strong evidence against a real spinning disk, which would top out one to two orders of magnitude
slower. The `rotational` flag simply wasn't correctly propagated through the virtio paravirtualization layer from
host to guest — the guest kernel defaulted to the conservative assumption (rotational) rather than confirming
non-rotational, and nothing in this setup corrected it.

## How It Actually Works

The `rotational` hint exists because the *correct* I/O scheduling and merging strategy genuinely differs between
device types: a spinning disk has real, significant seek latency, so grouping nearby-sector requests together
and minimizing head movement meaningfully helps; an SSD/NVMe device has no seek penalty at all, and aggressive
request merging can actually hurt by adding latency for no benefit, while the device's own deep internal queue
handles parallelism far better than the kernel reordering could. Historically, several userspace tools and even
some kernel defaults used this single flag to pick sane defaults automatically (certain filesystem mount options,
older default scheduler selection logic) — which is exactly why a wrong hint, as caught here, isn't purely
academic: it can lead the system toward scheduling decisions tuned for the wrong physical reality.

This happens because the information has to cross a real boundary: the *host's* kernel knows its underlying
storage is genuinely non-rotational flash, but the **virtio_blk** paravirtualized device presented to the guest
doesn't necessarily forward that fact — it's a property of the specific virtualization stack's device model,
not something a VM can discover with certainty on its own. This is a useful, general lesson about any
virtualized or containerized environment: hints and defaults the kernel ships, correct on real bare-metal
hardware, are not automatically trustworthy once another software layer is standing between your kernel and the
physical device — and the discrepancy is usually only visible if you deliberately check, as this lesson just did.

## Common mistakes

- **Trusting `rotational`, or any single hardware-hint file under `/sys/block/*/queue/`, without a sanity check
  in a virtualized environment.** As demonstrated, a VM's guest kernel can report a demonstrably wrong value for
  a property the host would get right — a raw throughput test (as done here) is a fast, concrete cross-check.
- **Changing the I/O scheduler without benchmarking the actual change.** `mq-deadline` vs `none` vs `bfq`
  genuinely does change behavior, but the *right* choice depends on real workload and device characteristics,
  not which one "sounds more modern" — measure before and after a change, on the real workload.
- **Treating one `dd` throughput number as a complete performance picture.** Sequential large-block writes (as
  shown here) can look excellent while small random I/O on the exact same device performs very differently — a
  single benchmark number is a data point, not a full characterization.

## Exercise

Check `/sys/block/<your root device>/queue/rotational` and `.../scheduler` on any Linux machine you have access
to — physical, virtual, or cloud — and reason about whether the reported value matches what you know (or can
infer via a quick `dd` throughput test) about the real underlying storage. If you find a mismatch like this
lesson's, that's a genuine, useful finding worth noting, not a sign you did something wrong.
