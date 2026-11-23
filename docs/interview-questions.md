---
title: "Linux Interview Questions and Answers (178 Questions)"
description: "178 Linux interview questions with answers and explanations, from beginner to advanced, organised by level. Free, from the Linux Mastery Path."
---

# Linux Interview Questions and Answers

**178 questions** with the correct answer and a short explanation, organised from beginner (Level 1) to advanced (Level 4). Every question comes from a lesson in the free Linux Mastery Path, so you can open the lesson to go deeper.

!!! tip "Practise, don't just read"
    Each lesson also ends with an interactive quiz, and the [final quiz](quiz.md) tests all four levels. Try to answer each question below before reading the answer.

## Level 1 · The Kernel, Filesystem & Permissions

### [01 · What Linux Actually Is: Kernel, Distros &amp; the Unix Philosophy](level-1/01-what-linux-is.md)

**Q1.** What is "Linux" in the strictest sense?

**Answer:** The kernel only

The kernel is a single program that schedules processes, manages memory, talks to hardware and implements the filesystem abstraction. `uname -r` shows the kernel build.

**Q2.** What does a distro (distribution) add around the kernel?

**Answer:** A package manager, init system, standard directories, default config and curated packages

Debian, Ubuntu, Fedora, Arch and Alpine ship the same kernel source but differ above it.

**Q3.** How do ordinary programs like bash or ls touch hardware?

**Answer:** By asking the kernel through a system call, since they run in unprivileged user mode

Only the kernel runs in privileged mode.

**Q4.** Why can some scripts that work elsewhere break on Alpine?

**Answer:** It swaps GNU coreutils and glibc for BusyBox and musl

That substitution changes behaviour of some tools and libraries.

### [02 · The Boot Process: Firmware, Bootloader &amp; initramfs](level-1/02-boot-process.md)

**Q5.** What is the order of boot stages?

**Answer:** Firmware, bootloader, kernel, initramfs, switch_root to systemd (PID 1)

Each stage fails in a recognizable way.

**Q6.** What is initramfs?

**Answer:** A temporary root filesystem in RAM with just enough tools (udev, disk/RAID/LUKS drivers) to find and mount the real root

The real root may be on an encrypted LVM volume.

**Q7.** What does UEFI read boot entries from?

**Answer:** An EFI System Partition (a small FAT32 partition)

Legacy BIOS scanned a disk's first sector.

**Q8.** What does switch_root do?

**Answer:** Replaces the initramfs root with the real root filesystem and execs the init system as PID 1

On most modern distros that's systemd.

### [03 · The Filesystem Hierarchy &amp; Virtual Filesystems (/proc, /sys)](level-1/03-filesystem-hierarchy.md)

**Q9.** Where is system-wide configuration usually found?

**Answer:** /etc, almost always plain text

If you're hunting for where X is configured, start in /etc.

**Q10.** What belongs in /var?

**Answer:** Data that changes while the system runs: logs, caches, spool files

For example /var/log and /var/cache.

**Q11.** What are /proc and /sys?

**Answer:** Virtual filesystems, not files on disk

`stat -f /proc` reports Type: proc with zero blocks.

**Q12.** Why is /root kept separate from /home?

**Answer:** So the superuser's home is never accidentally on a separate, possibly-unavailable mount

/home holds regular users' directories.

### [04 · Files, Inodes &amp; Links: How Linux Actually Stores Data](level-1/04-inodes-links.md)

**Q13.** What does an inode NOT store?

**Answer:** The filename

The name lives in a directory entry, a (filename, inode number) pair in the parent directory.

**Q14.** After `ln original.txt hardlink.txt`, how do the two relate?

**Answer:** Two names for the same inode, and stat shows Links: 2

ls -i shows the same inode number, 135 in the lesson.

**Q15.** What happens to a symlink if you delete its target?

**Answer:** It breaks: cat gives 'No such file or directory'

A symlink is a separate tiny file whose content is just a path.

**Q16.** After rm original.txt, does cat hardlink.txt still work?

**Answer:** Yes, because the inode survives while another link exists

The data is freed when the link count reaches zero (and no process has it open).

### [05 · Users, Groups &amp; the Permission Model](level-1/05-users-permissions.md)

**Q17.** Does the kernel know usernames?

**Answer:** No: it checks numeric UIDs/GIDs, and /etc/passwd and /etc/group are just lookup tables for humans

If a user is deleted while their UID still owns files, ls -l shows the bare number.

**Q18.** In which order does the kernel check permission classes, and what happens at the first match?

**Answer:** Owner, then group, then other; it stops at the first match

So an owner with a more restrictive owner row than 'other' still gets only the owner row.

**Q19.** In the lesson, with mode 311 (-wx--x--x) on a directory, what works for its owner?

**Answer:** cat project/notes.txt works, but ls project is denied, because there's no read bit

Read on a directory allows listing names; execute allows traversing into it.

**Q20.** What does execute (x) mean on a directory?

**Answer:** Permission to traverse it (access entries by name)

Listing requires read (r).

### [06 · Advanced Permissions: SUID, SGID, Sticky Bit &amp; ACLs](level-1/06-suid-sgid-acls.md)

**Q21.** Why can an unprivileged user run /usr/bin/passwd and update /etc/shadow?

**Answer:** It's owned by root with the SUID bit, so it runs with the owner's UID

The `s` in -rwsr-xr-x marks SUID.

**Q22.** What does SGID on a directory do?

**Answer:** New files inside inherit the directory's group instead of the creator's primary group

The standard way to make a shared team directory.

**Q23.** What does the sticky bit (t) do on a directory like /tmp?

**Answer:** Only a file's owner can delete or rename it, regardless of write permission on the directory

/tmp is drwxrwxrwt.

**Q24.** What is mode 2775 on team-shared (after chgrp testeng)?

**Answer:** rwxrwsr-x with SGID, so files created there get group testeng

The lesson's touch team-shared/report2.txt shows group testeng.

### [07 · Processes 101: PIDs, fork/exec &amp; the Process Tree](level-1/07-processes-101.md)

**Q25.** What do fork() and exec() each do?

**Answer:** fork copies the calling process (new PID); exec replaces the program in the same PID

The shell uses fork then exec to start every command.

**Q26.** What values does fork() return?

**Answer:** 0 to the child, and the child's PID to the parent

This tells the two processes apart.

**Q27.** What is special about PID 1?

**Answer:** It's the one process the kernel starts directly during boot (systemd), with PPID 0, and everything else descends from it

Losing it is fatal.

**Q28.** Why do kernel worker threads like kworker appear in brackets in ps?

**Answer:** They're created by the kernel (children of kthreadd, PID 2), not by fork/exec from userspace, and have no real command line

ps -ef --forest draws the tree by PPID.

### [08 · Standard Streams, File Descriptors &amp; Pipes](level-1/08-streams-descriptors-pipes.md)

**Q29.** What are file descriptors 0, 1 and 2 by convention?

**Answer:** stdin, stdout and stderr

It's a convention the kernel doesn't enforce.

**Q30.** What does `cmd > file 2>&1` do?

**Answer:** Points fd 1 at the file, then fd 2 at wherever fd 1 now points, so both go to the file

The lesson's first ls /nonexistent wrote the error into cmd.log.

**Q31.** What does `cmd 2>&1 > file` do?

**Answer:** stderr goes to where stdout pointed (the terminal) first, then stdout goes to the file, so errors still print to the terminal

Order matters: the second run left cmd2.log empty.

**Q32.** How can you inspect a process's open descriptors?

**Answer:** ls -l /proc/&lt;pid&gt;/fd, a directory of symlinks, one per descriptor

fd 0 pointed to /dev/null in the example.

### [09 · Package Management Internals: dpkg/APT vs RPM/DNF](level-1/09-package-management-internals.md)

**Q33.** What is the difference between dpkg and APT?

**Answer:** dpkg installs .deb files and keeps the on-disk database but resolves nothing; APT fetches from repositories and resolves dependency graphs, then hands installation to dpkg

rpm and DNF split the same way for the Red Hat lineage.

**Q34.** What does `dpkg -L curl` show?

**Answer:** The package's exact file manifest, which is what apt remove deletes and nothing more

dpkg -S /usr/bin/curl does the reverse: which package owns a file.

**Q35.** What three things does 'install this package' really involve?

**Answer:** Unpack files, record which files belong to the package, and verify dependencies

The record is what makes clean uninstalls possible.

**Q36.** What does `apt-cache depends curl` list?

**Answer:** Its dependencies, such as libcurl4t64, libc6 and zlib1g

APT resolves that whole graph.

### [10 · Project: Build and Boot a Minimal Root Filesystem](level-1/10-project-minimal-rootfs.md)

**Q37.** What does debootstrap do?

**Answer:** Downloads and unpacks just enough .deb packages into a target directory to make a minimal root filesystem, without booting anything

Debian and Ubuntu installers use it internally.

**Q38.** Why does debootstrap have a second stage that runs inside chroot?

**Answer:** So package postinst scripts execute in the new filesystem's environment rather than against the host

The first stage unpacks core packages.

**Q39.** What does --variant=minbase mean?

**Answer:** The smallest useful set of packages rather than a full default install

--arch lets you build for another architecture, such as arm64 for a Raspberry Pi.

**Q40.** Why bind-mount /dev and mount proc and sysfs inside the chroot?

**Answer:** So tools inside see device nodes and the /proc and /sys virtual filesystems

The chroot reported Ubuntu 24.04 while the host was 26.04.

## Level 2 · Processes, Memory & Storage

### [01 · Process States, Signals &amp; Job Control](level-2/01-process-states-signals.md)

**Q41.** What does state D mean, and can SIGKILL stop it?

**Answer:** Uninterruptible sleep, usually waiting on disk I/O; it can't be killed until the I/O completes

The kernel considers the operation too delicate to abort.

**Q42.** What is a zombie (Z) process?

**Answer:** A process that has exited but whose parent hasn't collected its exit status; kill -9 can't remove it

It has no running code left to signal. The parent must wait() or die.

**Q43.** What do kill -STOP and kill -CONT do?

**Answer:** Move a process between S (sleeping) and T (stopped), like Ctrl-Z and fg/bg

The lesson showed S → T → S with ps.

**Q44.** What is a signal, per the lesson?

**Answer:** Not a forceful interrupt but a flag the kernel sets that the target process, if in a position to, gets a chance to act on

That's why kill -9 sometimes does nothing.

### [02 · Scheduling: Nice, Priorities &amp; the CFS](level-2/02-scheduling-cfs.md)

**Q45.** What does a higher nice value mean?

**Answer:** More generous to others: a smaller claim on the CPU (range -20 to 19)

Default is 0; -20 is the most aggressive.

**Q46.** In the lesson's ps output, how does PRI relate to NI?

**Answer:** Lower PRI tracks higher (less favourable) nice: nice 0 showed PRI 19, nice 10 showed 9, nice 15 showed 4

ni is what you set; pri is procps's view of the kernel-level priority.

**Q47.** What does renice do?

**Answer:** Changes the niceness of an already running process, e.g. to deprioritise a batch job without restarting it

Raising priority (lower nice) requires root.

**Q48.** What does `chrt -p $$` report for a normal shell?

**Answer:** SCHED_OTHER, the default time-shared policy

SCHED_FIFO and SCHED_RR are real-time policies.

### [03 · Memory Management: Virtual Memory, Paging &amp; the OOM Killer](level-2/03-memory-management.md)

**Q49.** Why does `free -h` show a tiny 'free' but a large 'available'?

**Answer:** Much of memory is used as reclaimable page cache (buff/cache), which the kernel can free when needed

In the lesson, 1.0 GiB was free but 3.3 GiB available, with 2.5 GiB in buff/cache.

**Q50.** What does virtual memory give each process?

**Answer:** Its own private address space, mapped to physical pages by page tables (4 KiB pages on most systems)

It also enables fork's copy-on-write and swapping.

**Q51.** How was the OOM kill in the lesson triggered?

**Answer:** systemd-run --scope -p MemoryMax=100M ran a script in a memory-limited cgroup, and the kernel killed it (CONSTRAINT_MEMCG)

dmesg showed 'Memory cgroup out of memory: Killed process'.

**Q52.** What does the VM in the lesson lack that is common on cloud VMs and containers?

**Answer:** Swap (Swap: 0B)

free -h showed 3.8 GiB total and no swap.

### [04 · Disks &amp; Block Devices: Partitions, LVM &amp; Filesystems](level-2/04-disks-lvm-filesystems.md)

**Q53.** What are LVM's three layers?

**Answer:** Physical volumes (PVs) pooled into a volume group (VG), with logical volumes (LVs) carved out of the pool

An LV can span multiple physical disks.

**Q54.** Why does LVM make growing storage easier than partitions?

**Answer:** Growing an LV is a software operation against the VG's free space, not a disk-geometry problem

Partition resizing means shuffling data to make room.

**Q55.** How did the lesson simulate two physical disks?

**Answer:** Two 512 MB plain files attached as loop devices with losetup

The files became /dev/loop0 and /dev/loop1.

**Q56.** What order of commands builds a usable LVM filesystem?

**Answer:** pvcreate, vgcreate, lvcreate, mkfs.ext4, then mount

Then df -h confirms the mounted size (770M of an 800M LV after overhead).

### [05 · Mounting, fstab &amp; Network Filesystems](level-2/05-mounting-fstab-nfs.md)

**Q57.** What do the six fstab fields mean, in order?

**Answer:** Device, mount point, type, options, dump flag, fsck pass number

fsck pass 1 is for root, 2 for others, 0 for never.

**Q58.** Why identify a device by LABEL in fstab rather than /dev/vda1?

**Answer:** The label survives device renumbering

A hardcoded path breaks if /dev/vda1 becomes /dev/vda2.

**Q59.** What does a bind mount do?

**Answer:** Makes the same directory's contents visible at a second path; it's not a new filesystem

Writes through either path affect the same files; container runtimes use this to expose host directories.

**Q60.** How does findmnt differ from fstab?

**Answer:** findmnt shows the live mounts, which can differ from fstab if something was mounted by hand

fstab is a declarative list for boot time.

### [06 · systemd Deep Dive: Units, Targets &amp; Dependencies](level-2/06-systemd-deep-dive.md)

**Q61.** What is a target in systemd?

**Answer:** A special unit that groups other units as a synchronization point, like multi-user.target

Units declare WantedBy=multi-user.target to start as part of reaching it, which is how systemctl enable works.

**Q62.** What does After= in a unit file mean?

**Answer:** An ordering constraint only, not a dependency; Wants=/Requires= express need

ssh.service is deliberately tolerant of a not-fully-ready network.

**Q63.** What does ConditionPathExists=!/etc/ssh/sshd_not_to_be_run do?

**Answer:** A runtime gate: the unit is skipped if that file exists

The ! negates the condition.

**Q64.** Which unit type starts its service lazily on first connection?

**Answer:** .socket

A .timer is the scheduled-trigger unit.

### [07 · Writing systemd Services &amp; Timers](level-2/07-systemd-services-timers.md)

**Q65.** What problem does OnUnitActiveSec= avoid compared with cron?

**Answer:** A job overlapping itself, because it runs N seconds after the previous run finished

A 5-minute job scheduled every 5 minutes can overlap if one run takes 6 minutes under cron.

**Q66.** What does `Type=oneshot` on heartbeat.service mean?

**Answer:** It runs a command to completion and then becomes inactive (dead) until triggered again

systemctl status showed inactive (dead) with status=0/SUCCESS between timer runs.

**Q67.** What do you run to enable a timer and start it right now?

**Answer:** sudo systemctl enable --now heartbeat.timer

It creates the symlink under timers.target.wants.

**Q68.** Where does the service's output go with a timer-based job?

**Answer:** Through the normal journald pipeline, with no mail or separate logging setup

systemctl status also shows when it last ran and whether it succeeded.

### [08 · Logging &amp; journald: Structured Logs at the OS Level](level-2/08-journald-logging.md)

**Q69.** How does a journal entry differ from a syslog text line?

**Answer:** It's a structured record with named fields, several attached automatically by the journal

Examples: _UID, _GID, _BOOT_ID, _SYSTEMD_CGROUP.

**Q70.** Why can journalctl -u filter by unit even for programs that never use systemd APIs?

**Answer:** The filtering key comes from the environment the message was logged in (the cgroup/unit), not from parsing text

Programs writing to stdout or stderr under a unit still get unit, UID, GID, cgroup and boot ID fields.

**Q71.** What do CODE_FILE, CODE_FUNC and CODE_LINE show?

**Answer:** The source location, present only when the program uses sd_journal_print()-style calls

Plain stdout logging doesn't include them.

**Q72.** What does an existing /var/log/journal directory indicate?

**Answer:** Persistent journal storage (otherwise logs live in memory and are lost at reboot)

The lesson's `journalctl --disk-usage` showed 8M.

### [09 · Device Files, udev &amp; /dev](level-2/09-device-files-udev.md)

**Q73.** What do the leading c and b in ls -l on a device file mean?

**Answer:** c is a character device (stream); b is a block device (fixed-size blocks)

/dev/null is c; /dev/vda is b.

**Q74.** What do the major and minor numbers identify?

**Answer:** Major: which driver handles the device; minor: which specific instance the driver should talk to

/dev/null (1,3) and /dev/zero (1,5) share major 1 and differ by minor.

**Q75.** What does udev do?

**Answer:** Names newly detected devices and creates symlinks such as disk/by-path and disk/by-diskseq

udevadm info shows the S: symlink lines.

**Q76.** Why is /dev/vda major 253 in the lesson's VM?

**Answer:** It's a virtio_blk paravirtualised disk; real hardware would show a different major for its driver

The major identifies the driver.

### [10 · Project: Diagnose a Resource-Starved System](level-2/10-project-resource-diagnosis.md)

**Q77.** What does `ps -eo ... --sort=-pcpu` reveal about two cpu_hog.sh loops?

**Answer:** They're in state R at about 100% CPU each, dwarfing every other process

R means runnable: on a CPU or waiting for one.

**Q78.** Why did uptime's load average look low (0.00, 0.05, 0.04) right after starting the hogs?

**Answer:** Load average is an exponentially decaying moving average over 1/5/15 minutes, so it takes wall-clock time to rise

The samples were taken in the first couple of seconds.

**Q79.** In the vmstat output, what did the two hogs show?

**Answer:** us (user CPU) about 50% and id about 50%, with r = 2 runnable processes

A 2-CPU VM with two spinning loops uses half the CPU in user mode on average.

**Q80.** What does an infinite `while true; do :; done` loop simulate?

**Answer:** A process stuck in a bad loop or spinning instead of blocking on I/O: a realistic incident pattern

The kernel schedules it like any CPU-bound process.

## Level 3 · Networking & Security Internals

### [01 · The Linux Network Stack: Interfaces, IP &amp; Routing](level-3/01-network-stack-routing.md)

**Q81.** What is the loopback interface (lo) for?

**Answer:** Letting a machine talk to itself without touching real hardware

A real NIC, a virtual device or lo can each be an interface.

**Q82.** What does `scope link` on an address mean, versus `scope global`?

**Answer:** link is valid only on the local network segment (like IPv6 link-local); global is routable beyond this machine

The lesson's fe80:: address has scope link.

**Q83.** What does `dynamic` on an inet address indicate?

**Answer:** It came from DHCP, with valid_lft/preferred_lft lease timers, so it can change

Nothing on the system owns the IP permanently.

**Q84.** What does `ip route get 8.8.8.8` show?

**Answer:** The kernel's actual routing decision: next hop (via 192.168.5.2), interface and source address

Anything outside the local /24 uses the default route via the gateway.

### [02 · DNS Resolution on Linux: resolv.conf, nsswitch &amp; systemd-resolved](level-3/02-dns-resolution.md)

**Q85.** What does the hosts: files dns line in nsswitch.conf mean?

**Answer:** Check /etc/hosts first, then DNS

That's why a /etc/hosts entry overrides DNS.

**Q86.** Why does /etc/resolv.conf show nameserver 127.0.0.53?

**Answer:** It's systemd-resolved's local stub resolver; the real upstream server (192.168.5.2) is shown by resolvectl status

The file says 'Do not edit'.

**Q87.** What does resolvectl query github.com show?

**Answer:** One real resolution end to end: the address, the link, time taken and the protocol used

In the lesson: 22.2 ms via DNS.

**Q88.** Which layer is consulted first for any program calling getaddrinfo()?

**Answer:** nsswitch.conf's lookup order

resolv.conf comes into play only when resolution falls through to dns.

### [03 · Netfilter &amp; Firewalls: iptables vs nftables](level-3/03-netfilter-iptables-nftables.md)

**Q89.** What is Netfilter?

**Answer:** The kernel subsystem with hook points (prerouting, input, forward, output, postrouting) that iptables and nftables configure

Neither iptables nor nftables is netfilter itself.

**Q90.** What does `iptables -V` showing `(nf_tables)` mean?

**Answer:** The iptables command is a compatibility layer that translates rules into nftables

It doesn't touch the legacy ipt_* modules.

**Q91.** What does this nft rule do? `nft add rule inet demo input ip saddr 10.99.99.99 drop`

**Answer:** Drops incoming packets from source 10.99.99.99 in a chain attached to the input hook

The chain was created with type filter hook input.

**Q92.** Where did the LIMADNS chain in the VM's ruleset come from?

**Answer:** Lima's own networking setup, redirecting DNS traffic for the VM

nft list ruleset shows the system's actual configuration.

### [04 · Sockets, Ports &amp; the ss/netstat Toolset](level-3/04-sockets-ports-ss.md)

**Q93.** What does a LISTEN socket represent?

**Answer:** A server announcing it will accept new connections on a port; the kernel queues handshaken connections until accept()

ESTABLISHED is an active two-way conversation.

**Q94.** What uniquely identifies an ESTABLISHED connection?

**Answer:** The pairing of a local address:port with a remote address:port

The lesson showed both ends of 127.0.0.1:8899 and 127.0.0.1:38698.

**Q95.** What does `ss -tlnp` list?

**Answer:** TCP listening sockets with numeric ports and the owning process

-t TCP, -l listening, -n numeric, -p process.

**Q96.** What does listening on 0.0.0.0:22 versus 127.0.0.1:8899 mean?

**Answer:** 0.0.0.0 accepts on all interfaces; 127.0.0.1 accepts only local connections

systemd-resolved listens on 127.0.0.53 and 127.0.0.54 on port 53.

### [05 · SSH Internals: Keys, Agents &amp; the Protocol](level-3/05-ssh-internals.md)

**Q97.** What is the difference between a host key and a user key?

**Answer:** A host key proves the server's identity to you; a user key proves your authorisation to the server

authorized_keys and ssh-copy-id are built around user keys.

**Q98.** Why does SSH warn loudly 'REMOTE HOST IDENTIFICATION HAS CHANGED'?

**Answer:** A host key almost never changes, so a change could be re-provisioning or a man-in-the-middle, and SSH can't tell which

It catches both causes.

**Q99.** Why must the host private key be mode rw-------?

**Answer:** sshd refuses to use a key file with overly permissive permissions, and a readable private key defeats its purpose

The public key is world-readable, as it should be.

**Q100.** What does ssh-agent hold, and what does `ssh-add -l` list?

**Answer:** Loaded identities in memory; their fingerprints

It showed the demo-key's SHA256 fingerprint.

### [06 · Linux Security Modules: SELinux vs AppArmor](level-3/06-selinux-apparmor.md)

**Q101.** What question does a Linux Security Module answer that rwx permissions don't?

**Answer:** Can this specific program, regardless of which user runs it, do this specific thing — even for root

It's mandatory access control layered on top of owner/group/other.

**Q102.** How do AppArmor and SELinux differ?

**Answer:** AppArmor is path-based with per-executable profiles; SELinux is label-based with contexts (user:role:type:level)

AppArmor is Ubuntu/Debian's default; SELinux is Red Hat/Fedora's.

**Q103.** In the lesson, why did sshd show 'unconfined' while dig showed 'dig (enforce)'?

**Answer:** A profile exists and is enforced for dig but not for sshd on that system; having some profiles doesn't confine every process

/proc/&lt;pid&gt;/attr/current reveals a process's confinement.

**Q104.** What does aa-status report?

**Answer:** How many profiles are loaded and in enforce or complain mode

The lesson showed 180 loaded, 103 enforcing, 2 complain.

### [07 · Namespaces &amp; Cgroups: The Building Blocks of Containers](level-3/07-namespaces-cgroups.md)

**Q105.** What are the two mechanisms that make a container look isolated?

**Answer:** Namespaces (what a process can see) and cgroups (what it can use)

A container is a normal Linux process on the host kernel.

**Q106.** In the unshare PID-namespace demo, what PID did bash report for itself?

**Answer:** 1, genuinely what getpid() returns inside the namespace

ps aux inside saw only three processes.

**Q107.** Why was --mount-proc needed?

**Answer:** Otherwise /proc would still show the host's process table through the mount namespace

It mounts a fresh /proc for the new PID namespace.

**Q108.** Which namespace isolates the hostname, which plain chroot does not?

**Answer:** UTS

Others: network, user (UID/GID mapping), IPC and cgroup.

### [08 · Kernel Tuning: sysctl &amp; /proc Parameters](level-3/08-sysctl-kernel-tuning.md)

**Q109.** How does the sysctl name net.ipv4.ip_forward map to the filesystem?

**Answer:** /proc/sys/net/ipv4/ip_forward (dots become slashes)

Reading or writing the file has the identical immediate effect.

**Q110.** What does net.ipv4.ip_forward = 1 do?

**Answer:** Lets the kernel route packets between interfaces (an endpoint becomes a router)

sysctl -w takes effect immediately, no reboot.

**Q111.** How do you make a sysctl setting persist across reboots?

**Answer:** Put it in a file under /etc/sysctl.d/

For example 99-lima.conf.

**Q112.** What does net.ipv4.ip_unprivileged_port_start=0 do?

**Answer:** Lets unprivileged users bind ports below 1024

Ports under 1024 are traditionally root-only.

### [09 · Auditing &amp; Hardening: auditd and fail2ban](level-3/09-auditd-fail2ban-hardening.md)

**Q113.** What does `auditctl -w /etc/passwd -p wa -k passwd_watch` do?

**Answer:** Watches /etc/passwd for write and attribute-change access, tagging events with the key passwd_watch

touch caused one matching event.

**Q114.** What does an audit record give you that an inotify-style 'file changed' event doesn't?

**Answer:** A forensic record: process, real vs audit UID, syscall and success or failure, tied to a rule key

It's suited to compliance reviews and incident investigation.

**Q115.** What was the real tooling mismatch in the lab?

**Answer:** ausearch -k found nothing although grep found the event in the raw audit log

Probably a parsing mismatch between the ausearch version and the log format.

**Q116.** What lesson does the mismatch teach?

**Answer:** Know the raw log location (/var/log/audit/audit.log) and sanity-check a 'no matches' result against it

Otherwise you might believe a real event never happened.

### [10 · Project: Build a Container From Namespaces and Cgroups](level-3/10-project-mini-container.md)

**Q117.** What does the project combine to build a 'container' by hand?

**Answer:** unshare namespaces (PID, mount, UTS) and a cgroup v2 memory limit

No container runtime is involved.

**Q118.** How is the shell placed into the limited cgroup?

**Answer:** By writing its PID to the cgroup's cgroup.procs; memory.max sets the ceiling

Everything it spawns afterwards is in the group too.

**Q119.** What happened when python allocated memory past 50M?

**Answer:** The kernel OOM-killed it inside the cgroup (CONSTRAINT_MEMCG); the shell reported 'Killed'

dmesg showed 'Memory cgroup out of memory: Killed process'.

**Q120.** Why does hostname inside show minicontainer while the host still shows lima-linuxlab?

**Answer:** The UTS namespace isolates the hostname, unlike plain chroot

--uts adds it to the PID and mount namespaces.

## Level 4 · Performance, Troubleshooting & Capstone

### [01 · Performance Tools: top, vmstat, iostat &amp; free Explained](level-4/01-performance-tools.md)

**Q121.** In top's %Cpu(s), what does wa mean?

**Answer:** Time spent waiting on I/O: CPU idle but not free, something is blocked on disk or network

us is user mode, sy is kernel, id is genuinely idle.

**Q122.** Why is 'avail Mem' much larger than 'free' in top?

**Answer:** Reclaimable buff/cache counts as available

3340.9 available versus 1018.4 free in the lesson.

**Q123.** Why is iostat's %util misunderstood?

**Answer:** It measures time with outstanding I/O, not percent of disk capacity or throughput headroom; check await and aqu-sz too

Don't size storage decisions on it alone.

**Q124.** What does the `1 zombie` in top's Tasks line refer to?

**Answer:** The leftover sshd zombie seen in the earlier process-states lesson

A zombie is an exited process whose parent hasn't collected it.

### [02 · Tracing &amp; Profiling: strace, ltrace &amp; perf](level-4/02-strace-ltrace-perf.md)

**Q125.** What does strace show?

**Answer:** Every system call a running process makes

ltrace shows library calls; perf shows where CPU time goes.

**Q126.** What did `strace -c ls /tmp` reveal?

**Answer:** Even a simple command made 159 syscalls and hit 12 errors

Locale lookups, mmap of libraries and terminal checks add up.

**Q127.** What did strace show about cat's failed openat of a locale .ftl file?

**Answer:** ENOENT: a harmless lookup that cat silently tolerates before opening the real file

It answers 'why is this program touching that path' with evidence.

**Q128.** What does strace -e trace=open,openat do?

**Answer:** Filters output to just those syscalls

It makes long traces readable.

### [03 · Filesystem Performance &amp; I/O Scheduling](level-4/03-filesystem-performance-io.md)

**Q129.** When is the `none` I/O scheduler often the right choice?

**Answer:** For fast NVMe storage, where the device's own queues do better than software reordering

Reordering has a cost, and skipping it is correct when the device doesn't need help.

**Q130.** What does mq-deadline prioritise?

**Answer:** Fairness and bounded latency, so no request waits indefinitely

bfq optimises interactive responsiveness on slower devices.

**Q131.** Why was `rotational = 1` on a virtio disk surprising?

**Answer:** It tells the kernel it's a spinning disk, but the 1.4 GB/s throughput shows it's flash-backed; virtualisation made the hint unreliable

The flag wasn't correctly propagated through the virtual device.

**Q132.** What does nr_requests = 256 mean?

**Answer:** The queue depth the block layer holds before applying backpressure to the application

It's visible in /sys/block/vda/queue/.

### [04 · Kernel Modules: Loading, Building &amp; Debugging](level-4/04-kernel-modules.md)

**Q133.** What does `insmod hello.ko` do, and how do you confirm it loaded?

**Answer:** Loads the module into the running kernel; lsmod | grep hello shows it

The usage count of 0 means nothing depends on it, so rmmod is safe.

**Q134.** Where did the module's printk messages appear?

**Answer:** In the kernel log, via dmesg

One message on init, one on exit.

**Q135.** Why does the build need /lib/modules/$(uname -r)/build?

**Answer:** It compiles against the running kernel's real headers and build system

The Makefile calls make -C ... M=$(PWD) modules.

**Q136.** What were the two build warnings about?

**Answer:** The compiler and pahole versions differ from those that built the shipped kernel, usually harmless for simple modules but risky for complex ones

pahole generates BTF debug metadata.

### [05 · /proc and /sys as Debugging Tools](level-4/05-proc-sys-debugging.md)

**Q137.** What does `ls -l /proc/$PID/fd` reveal about a running process?

**Answer:** Exactly what it has open: files, sockets and pipes, without attaching a debugger

The example showed a listening socket (fd 3) and a file opened for writing (fd 4).

**Q138.** What does /proc/$PID/wchan show?

**Answer:** The kernel function the process is currently blocked in (e.g. hrtimer_nanosleep)

It matched time.sleep(60) in the script.

**Q139.** Why was reading /proc/$PID/syscall refused without sudo?

**Answer:** Yama's ptrace_scope only allows inspecting direct ancestors or descendants by default

sudo bypassed the restriction.

**Q140.** What does /proc/$PID/syscall show?

**Answer:** The raw syscall number and argument registers the process is currently inside

Syscall 115 on that architecture is nanosleep-family.

### [06 · Troubleshooting Boot Failures &amp; Recovery Mode](level-4/06-boot-failure-recovery.md)

**Q141.** How can you validate a new fstab line before a reboot?

**Answer:** Run mount -a, which attempts every entry as boot would

It caught a missing mount point in the lesson.

**Q142.** What happens at boot when a non-root fstab entry fails?

**Answer:** systemd can't reach the dependent target and drops to an emergency shell for a human to intervene

It doesn't silently continue in a broken state.

**Q143.** What are two common fstab failure modes?

**Answer:** The device doesn't exist, or the mount point doesn't exist (mkdir -p may be all that's missing)

Both can be tested on a running system.

**Q144.** What does journalctl --list-boots show?

**Answer:** The boots recorded in the journal; the VM had only one

It's the command to check earlier boots for a failure.

### [07 · Containers vs VMs: Where OS Fundamentals End and Virtualization Begins](level-4/07-containers-vs-vms.md)

**Q145.** What is a container, compared with a VM?

**Answer:** A normal process on the same running kernel with a restricted view of resources; a VM boots a separate kernel on virtualised hardware

There's exactly one kernel involved for a container.

**Q146.** Why is creating a container so fast?

**Answer:** It's just a new process with extra kernel bookkeeping (namespaces, a cgroup); `unshare --pid --mount-proc --fork true` took about 13 ms

A VM's boot measures in seconds to minutes.

**Q147.** How was the VM's boot time measured in the lesson?

**Answer:** systemd-analyze: kernel 317ms, initrd 1.3s, userspace about 2m45s (mostly cloud-init network wait)

A real kernel boot and full userspace startup are unavoidable costs.

**Q148.** What's a mistake in choosing between them?

**Answer:** Choosing a VM 'to be safe' where properly configured container isolation would suffice

The right tool depends on the isolation needed.

### [08 · Linux Distros Compared: Debian, RHEL, Arch &amp; Alpine](level-4/08-distros-compared.md)

**Q149.** What differs between mainstream distros, and what doesn't?

**Answer:** Package manager, release model and defaults differ; kernel and systemd features like permissions, namespaces and netfilter are the same

The lesson is documentation-based because it can't be verified on one distro.

**Q150.** How do Fedora and RHEL relate?

**Answer:** Fedora is the fast-moving upstream; RHEL (and Rocky, AlmaLinux) is the long-support downstream built from a Fedora base

It mirrors Ubuntu's LTS philosophy.

**Q151.** What is Arch Linux's release model?

**Answer:** Rolling release: there is no 'Arch 26.04'; the system continuously updates (pacman)

The philosophy differs from Debian and RHEL.

**Q152.** Which default LSM do Ubuntu/Debian and RHEL/Fedora use?

**Answer:** AppArmor for Debian/Ubuntu; SELinux for RHEL/Fedora

Both use systemd init.

### [09 · Kernel Versions, LTS &amp; Staying Current](level-4/09-kernel-versions-lts.md)

**Q153.** What are the three kernel.org lines?

**Answer:** Mainline (newest, least tested), stable (bugfix backports for a few months) and longterm (bugfixes for years)

Distros and embedded systems build on longterm lines.

**Q154.** Is the newest longterm kernel the newest mainline release?

**Answer:** No: LTS is a deliberate choice for specific releases (6.18 longterm versus 7.3 mainline in the data)

A kernel needn't be the newest to be fully supported.

**Q155.** How many longterm lines were receiving updates in the lesson's data?

**Answer:** Six (from 5.10 through 6.18)

It was fetched live from kernel.org/releases.json.

**Q156.** Why does the lesson fetch live release data?

**Answer:** Version numbers go stale, so check current data rather than memory

The output will look different by the time you read it.

### [10 · Capstone: Build, Harden &amp; Diagnose a Linux Server From Scratch](level-4/10-capstone-server-build.md)

**Q157.** What makes `appuser` a least-privilege setup?

**Answer:** A dedicated user with key-only SSH (authorized_keys 600, .ssh 700, no password) running the service

The service also runs as appuser under systemd.

**Q158.** What does curl returning 000 mean when the service is stopped?

**Answer:** No HTTP status at all: nothing is accepting the connection, so check systemctl status (inactive (dead))

It points away from an HTTP-level problem.

**Q159.** What does Fault 2 in the lesson illustrate?

**Answer:** A firewall rule silently dropping a port that is listening, which ss -tln shows as LISTEN while connections still fail

The listener exists, but the packets never reach it.

**Q160.** Which pieces does the capstone combine?

**Answer:** Users and SSH keys, a systemd service, an nftables rule, and diagnosis with the course's tools

Three faults were injected on purpose and diagnosed.

## Mixed questions across all levels

**Q161.** A directory has mode 311 (d-wx--x--x) and you are its owner. `ls project` fails with 'Permission denied' but `cat project/notes.txt` works. Why?

**Answer:** There is no read bit, so listing names is denied, but execute lets you traverse into it by name

Read on a directory lists names; execute allows access by name. Verified: chmod 311 gives d-wx--x--x.

**Q162.** With umask 022, what modes do a new file and a new directory get? With umask 077?

**Answer:** 022: file 644, directory 755. 077: file 600, directory 700

New files start at 666 and directories at 777, minus the umask. Verified by creating them: 644/755 and 600/700.

**Q163.** A shared project directory should make every new file belong to the team group automatically. Which setting?

**Answer:** SGID on the directory (chmod 2775, group set to the team): drwxrwsr-x

SGID on a directory makes new files inherit the directory's group. Verified: chmod 2775 shows drwxrwsr-x.

**Q164.** Anyone may create files in /tmp but only a file's owner may delete it. Which bit, and how does it appear?

**Answer:** The sticky bit, shown as t: drwxrwxrwt (mode 1777)

Verified: chmod 1777 gives drwxrwxrwt.

**Q165.** `ls -l /usr/bin/passwd` shows -rwsr-xr-x root root. What does the s mean for a normal user running it?

**Answer:** The program runs with the file owner's (root's) UID, so it can update /etc/shadow

SUID applies for the lifetime of that process only.

**Q166.** You run `ln original.txt hardlink.txt` and `ln -s original.txt symlink.txt`, then `rm original.txt`. What happens?

**Answer:** cat hardlink.txt still works (the inode survives with 1 link); the symlink is broken

A hard link is another name for the same inode; a symlink stores a path. Verified by running the commands: link count 2 → 1, hardlink prints hello, symlink broken.

**Q167.** `ls /nonexistent 2>&1 > cmd.log` leaves cmd.log empty and prints the error to the screen. Why?

**Answer:** stderr was duplicated onto the terminal first; only afterwards was stdout redirected to the file

Redirections apply left to right. `> cmd.log 2>&1` captures both. Verified by running both orders.

**Q168.** A process shows state Z in ps and `kill -9` does nothing. What is it, and what removes it?

**Answer:** A zombie: it already exited, so there's nothing to signal; the parent must collect its status (or die, so init reaps it)

A zombie is just an exit-status record.

**Q169.** A process is stuck in state D (uninterruptible sleep) on disk I/O. Will SIGKILL end it immediately?

**Answer:** No: it can't be killed until the I/O completes

The kernel considers the operation too delicate to abort.

**Q170.** `free -h` shows 1.0Gi free but 3.3Gi available. Is the system low on memory?

**Answer:** No: much of it is reclaimable page cache (buff/cache), which counts as available

Look at available, not free.

**Q171.** A service must run 'every 5 minutes' without overlapping itself if a run takes 6 minutes. Which mechanism fits best?

**Answer:** A systemd timer using OnUnitActiveSec= (runs after the previous run finished)

OnUnitActiveSec counts from the end of the last run. Output also goes to journald.

**Q172.** You added a new line to /etc/fstab. How do you check it without rebooting?

**Answer:** Run `sudo mount -a`, which attempts every entry as boot would

A bad non-root entry can drop the next boot into an emergency shell.

**Q173.** `/etc/resolv.conf` says `nameserver 127.0.0.53`. Where do DNS queries really go?

**Answer:** To systemd-resolved's local stub, which forwards them to the upstream server shown by `resolvectl status`

nsswitch.conf's hosts: files dns line decides that /etc/hosts is checked first.

**Q174.** A service is listening on port 9090 (`ss -tln` shows it), but remote connections time out while local ones work. What is the most likely cause?

**Answer:** A firewall rule dropping the port (check nft list ruleset / iptables)

The capstone's Fault 2: the socket is LISTENing, yet packets never reach it.

**Q175.** `curl` returns HTTP status 000 for your service. What does it tell you?

**Answer:** No HTTP exchange took place: nothing accepted the connection (service stopped, wrong port or firewall), so check the service and socket first

Status 000 means curl got no HTTP response.

**Q176.** Which two kernel mechanisms make a process look like a container, and what does each do?

**Answer:** Namespaces limit what it can see (PID, mount, UTS, network, user…); cgroups limit what it can use (CPU, memory…)

A container is a normal process on the host kernel.

**Q177.** A process in a cgroup with memory.max=50M tries to allocate more. What happens?

**Answer:** The kernel OOM-kills it inside the cgroup (CONSTRAINT_MEMCG); the host keeps running

dmesg shows 'Memory cgroup out of memory: Killed process'.

**Q178.** Why does `iptables -V` print (nf_tables) on modern distros?

**Answer:** iptables is a compatibility front end that translates rules into nftables, both configuring netfilter's hooks

Neither tool is netfilter itself.

## Practical coding questions

### Redirection order

Using the emit function (writes one line to stdout and one to stderr), write redirections so that: A) both streams end up in both.log, B) stdout goes to out.log and stderr to err.log, C) demonstrate the common mistake by writing `2>&1` BEFORE `> wrong.log`, capturing what leaks to the terminal with $( ). Print the results exactly as shown in the expected output.

Starter code:

```
emit() { echo "to stdout"; echo "to stderr" >&2; }

# A: send both streams into both.log
emit # your redirection here
echo "A: $(wc -l < both.log | tr -d ' ') lines"

# B: stdout to out.log, stderr to err.log
emit # your redirection here
echo "B: out=[$(cat out.log)] err=[$(cat err.log)]"

# C: wrong order
leaked=$(emit) # your redirection here
echo "C: leaked=[$leaked] wrong.log=[$(cat wrong.log)]"
```

Expected output:

```text
A: 2 lines
B: out=[to stdout] err=[to stderr]
C: leaked=[to stderr] wrong.log=[to stdout]
```

??? success "Show a solution"

    ```
    emit() { echo "to stdout"; echo "to stderr" >&2; }

    # A: send both streams into both.log
    emit > both.log 2>&1
    echo "A: $(wc -l < both.log | tr -d ' ') lines"

    # B: stdout to out.log, stderr to err.log
    emit > out.log 2> err.log
    echo "B: out=[$(cat out.log)] err=[$(cat err.log)]"

    # C: wrong order - stderr is duplicated onto the terminal (here, captured by $( ))
    leaked=$(emit 2>&1 > wrong.log)
    echo "C: leaked=[$leaked] wrong.log=[$(cat wrong.log)]"
    ```

    `> file 2>&1` points fd 1 at the file and then fd 2 at wherever fd 1 now points. With `2>&1 > file`, fd 2 is duplicated onto the terminal first, so errors still leak. Verified by running the solution in bash: output matches.

### Hard link versus symlink

Create original.txt containing hello, a hard link hardlink.txt and a symlink symlink.txt. Print the link count of original.txt, delete the original, then show whether the hard link and the symlink still work and the link count that remains.

Starter code:

```
echo hello > original.txt
# create a hard link and a symlink to original.txt

echo "links before: $(ls -l original.txt | awk '{print $2}')"
rm original.txt
echo "hardlink: $(cat hardlink.txt)"
if [ -e symlink.txt ]; then echo "symlink: works"; else echo "symlink: broken"; fi
echo "links after: $(ls -l hardlink.txt | awk '{print $2}')"
```

Expected output:

```text
links before: 2
hardlink: hello
symlink: broken
links after: 1
```

??? success "Show a solution"

    ```
    echo hello > original.txt
    ln original.txt hardlink.txt
    ln -s original.txt symlink.txt
    echo "links before: $(ls -l original.txt | awk '{print $2}')"
    rm original.txt
    echo "hardlink: $(cat hardlink.txt)"
    if [ -e symlink.txt ]; then echo "symlink: works"; else echo "symlink: broken"; fi
    echo "links after: $(ls -l hardlink.txt | awk '{print $2}')"
    ```

    A hard link is a second directory entry for the same inode (link count 2), so the data survives rm. A symlink is a separate tiny file holding a path, which breaks when the target disappears. Verified by running the solution in bash: output matches.

---

More free practice: the [Linux Mastery Path](index.md) curriculum, the [Interview Prep Pack](https://learnmasterypath.com/interview-pack/) and the [free resume ATS check](https://learnmasterypath.com/resume/).
