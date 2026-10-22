---
description: "Least privilege on Linux: capabilities, SELinux, AppArmor and seccomp, with a tested capability-mask decoder."
---

# 07 · Capabilities, SELinux & AppArmor

"Run as root or don't" is too coarse. A web server needs to bind port 443 but has no business loading kernel modules. Linux provides layers that shrink what even a compromised process can do: **capabilities** (divide root's power), **mandatory access control** (SELinux or AppArmor: a policy enforced regardless of file
permissions), and **seccomp** (restrict system calls). Container runtimes and systemd's sandboxing options are built from exactly these.

!!! note "What was run"
    Capability, SELinux, AppArmor and seccomp tooling is Linux-only and **was not run**. Descriptions come from `capabilities(7)` (man7.org, October 2026) and general documentation of SELinux/AppArmor. A **Python capability-mask decoder was run with 6 pytest tests passing on macOS**; the capability *names* were verified against `capabilities(7)` (all 41 appear
    there), but the bit *numbers* come from my memory of `linux/capability.h` and I did not re-check them against the header. The masks in the examples are fixtures I built, not from a real process. See Level 1 · Lesson 01.

## Capabilities: root, divided

Traditionally the kernel checked "is the UID 0?" before privileged operations. Since Linux 2.2, those powers are split into **capabilities** that can be granted individually. A few of the roughly forty (names verified against `capabilities(7)`):

| Capability | Allows |
|---|---|
| `CAP_NET_BIND_SERVICE` | "Bind a socket to Internet domain privileged ports (port numbers less than 1024)" |
| `CAP_NET_RAW` | RAW and PACKET sockets (ping, packet capture) |
| `CAP_NET_ADMIN` | Network configuration, firewall, routing |
| `CAP_CHOWN`, `CAP_FOWNER`, `CAP_DAC_OVERRIDE` | Change owners; bypass ownership/permission checks on files |
| `CAP_KILL`, `CAP_SETUID`, `CAP_SETGID` | Signal any process; change UID/GID |
| `CAP_SYS_ADMIN` | A huge grab-bag (mounts, namespaces, many ioctls): treat as "nearly root" |
| `CAP_SYS_PTRACE`, `CAP_SYS_MODULE`, `CAP_SYS_RAWIO`, `CAP_BPF`, `CAP_PERFMON` | Debug other processes; load modules; raw I/O; BPF; performance monitoring |

### The five sets per process

Each process has capability sets in `/proc/<pid>/status` as hexadecimal masks:

| Line | Set | Meaning |
|---|---|---|
| `CapEff` | Effective | What the kernel actually checks for permission |
| `CapPrm` | Permitted | The limit on what the process may add to effective |
| `CapInh` | Inheritable | What can be passed through `execve` (with file inheritable caps) |
| `CapBnd` | Bounding | A cap on what can ever be gained via `execve`; containers shrink this |
| `CapAmb` | Ambient | Kept across `execve` of unprivileged programs (since Linux 4.3) |

Files can carry capabilities too: `setcap cap_net_bind_service=+ep /usr/local/bin/myserver` lets that one binary bind low ports **without being setuid root** (compare Level 1 · 04). `getcap -r /usr/bin` lists them. systemd gives the same effect to a service with `AmbientCapabilities=CAP_NET_BIND_SERVICE` and `CapabilityBoundingSet=CAP_NET_BIND_SERVICE` (Level 2 · 02),
the recommended way to run a service on port 443 as an unprivileged user.

### A decoder (run)

```python
"""Decode the hexadecimal capability masks shown in /proc/<pid>/status (CapInh, CapPrm, CapEff, CapBnd, CapAmb).
Bit numbers follow linux/capability.h as I remember them; the NAMES were checked against capabilities(7)."""
CAPS = ("CHOWN DAC_OVERRIDE DAC_READ_SEARCH FOWNER FSETID KILL SETGID SETUID SETPCAP LINUX_IMMUTABLE NET_BIND_SERVICE NET_BROADCAST "
        "NET_ADMIN NET_RAW IPC_LOCK IPC_OWNER SYS_MODULE SYS_RAWIO SYS_CHROOT SYS_PTRACE SYS_PACCT SYS_ADMIN SYS_BOOT SYS_NICE "
        "SYS_RESOURCE SYS_TIME SYS_TTY_CONFIG MKNOD LEASE AUDIT_WRITE AUDIT_CONTROL SETFCAP MAC_OVERRIDE MAC_ADMIN SYSLOG WAKE_ALARM "
        "BLOCK_SUSPEND AUDIT_READ PERFMON BPF CHECKPOINT_RESTORE").split()

def decode(hexmask):
    m = int(hexmask, 16)
    names = ["CAP_" + n for i, n in enumerate(CAPS) if m >> i & 1]
    unknown = [i for i in range(len(CAPS), 64) if m >> i & 1]
    return names, unknown

def encode(*names):
    m = 0
    for n in names: m |= 1 << CAPS.index(n.removeprefix("CAP_"))
    return f"{m:016x}"

DANGEROUS = {"CAP_SYS_ADMIN": "close to root: mounts, namespaces, many ioctls", "CAP_SYS_PTRACE": "inspect/modify other processes' memory",
             "CAP_SYS_MODULE": "load kernel modules", "CAP_DAC_OVERRIDE": "bypass file permission checks", "CAP_NET_ADMIN": "reconfigure networking, firewall",
             "CAP_SYS_RAWIO": "raw device access", "CAP_BPF": "load BPF programs", "CAP_SETUID": "become any user", "CAP_SETFCAP": "grant file capabilities"}

def review(hexmask):
    names, unknown = decode(hexmask)
    return [(n, DANGEROUS[n]) for n in names if n in DANGEROUS], names
```

Output of the checks:

```text
decode("0000000000000400")                   -> (['CAP_NET_BIND_SERVICE'], [])
encode(NET_BIND_SERVICE, CHOWN, SETUID, SETGID) -> 00000000000004c1
decode("000001ffffffffff")                   -> 41 names, from CAP_CHOWN ... CAP_BPF, CAP_CHECKPOINT_RESTORE; unknown bits: []
review({NET_ADMIN, SYS_ADMIN, KILL})         -> [('CAP_NET_ADMIN', 'reconfigure networking, firewall'), ('CAP_SYS_ADMIN', 'close to root: mounts, namespaces, many ioctls')]
6 passed (pytest)
```

So a fully privileged root on a kernel with 41 capabilities has `CapEff: 000001ffffffffff` (the fixture value I built; the number of capabilities grows as the kernel adds them, so `CAP_LAST_CAP` in `/proc/sys/kernel/cap_last_cap` is the authority on a given machine), and a process holding only the low-port privilege shows `0000000000000400`. When reviewing a container,
`grep Cap /proc/<pid>/status` and decode `CapEff`/`CapBnd`; **anything containing SYS_ADMIN deserves scrutiny**, and `--privileged` containers have all of them.

The decoder tells you *which* bits are set but not whether each is needed; judging that is the human part, and the table above is the review checklist.

## Mandatory access control: SELinux and AppArmor

Ordinary permissions (Level 1 · 04) are *discretionary*: the owner decides. **Mandatory access control (MAC)** adds a system-wide policy that even root-owned processes can't override, so a compromised web server can't read `/etc/shadow` even if the file permissions would allow it (for example, running as root).

| | SELinux | AppArmor |
|---|---|---|
| Model | Labels on every process and file (`user:role:type:level`); policy states which *types* may do what | Path-based profiles per program |
| Default on | RHEL, Fedora, CentOS-family | Ubuntu, Debian (when enabled), SUSE |
| Strength | Very fine-grained, label-based (survives renames) | Simpler to write and read |
| Cost | Steeper learning curve | Path-based, less comprehensive |

Operating them (commands from their man pages, not run):

```bash
getenforce ; sestatus                      # SELinux mode: Enforcing / Permissive / Disabled
ls -Z /var/www ; ps -eZ | grep nginx       # labels
sudo ausearch -m avc -ts recent            # denials from the audit log
sudo setsebool -P httpd_can_network_connect on
sudo restorecon -Rv /var/www/html          # reset labels after moving files (a classic fix)
sudo aa-status ; sudo aa-complain /etc/apparmor.d/usr.sbin.nginx
```

The classic failure: a service works from the command line but fails under systemd with "Permission denied", with correct Unix permissions. **Check the MAC logs** (`ausearch`, `journalctl -t audit`, `dmesg | grep -i apparmor`) before touching `chmod`. **Do not disable SELinux/AppArmor to make something work**; use permissive mode (`setenforce 0`
temporarily) or complain mode to learn what the policy blocks, then add the right rule or boolean. Files moved with `mv` keep their old label; copied files take the destination's, which is why `restorecon` fixes "it worked before I moved it".

## seccomp: restricting system calls

A **seccomp** filter (Lesson 01) lets a process, once installed, make only an allowed set of system calls; others return an error or kill the process. Docker applies a default profile (blocking dozens of risky calls); systemd offers `SystemCallFilter=@system-service`; browsers sandbox renderers this way. It shrinks the kernel attack surface a compromised process
can reach, complementing capabilities (what privileges) and MAC (what objects).

## Layered sandboxing in practice

| Layer | Limits | systemd / container knob |
|---|---|---|
| User | Not root | `User=`, `DynamicUser=`, `USER` in the Dockerfile |
| Capabilities | Privileged operations | `CapabilityBoundingSet=`, `AmbientCapabilities=`, `--cap-drop=ALL --cap-add=...` |
| Namespaces | What it sees | `PrivateTmp=`, `ProtectSystem=`, `PrivateNetwork=` (Lesson 06) |
| cgroups | Resources | `MemoryMax=`, `CPUQuota=`, `TasksMax=` |
| MAC | Objects accessed | SELinux/AppArmor profile |
| seccomp | System calls | `SystemCallFilter=`, container seccomp profile |
| `NoNewPrivileges` | Gaining privilege via setuid/file caps | `NoNewPrivileges=yes`, `--security-opt no-new-privileges` |

Each layer is imperfect; stacked, they make the difference between "an attacker got code execution in the web process" and "an attacker got the machine".

## How It Actually Works

The kernel's permission checks call `capable(CAP_X)` (or `ns_capable` within a user namespace) instead of testing the UID against 0. At `execve`, the kernel recomputes the new process's sets from the old ones and the program's file capabilities using documented transformation rules (which is why `NoNewPrivileges` can block gains). Security modules (SELinux, AppArmor)
register hooks (the **LSM** framework) at many points: file open, socket create, `ptrace`, `exec`, and each hook is asked "allow?" after the normal DAC check passes; both must agree. SELinux looks up the (source type, target type, class, permission) tuple in its in-kernel policy database, with an access vector cache for speed; AppArmor matches the path against the
profile's rules. Denials are logged through the audit subsystem.

## Common mistakes

- **Running services as root** just to bind port 80/443.
- **`setcap` or `AmbientCapabilities` with far more than needed**, or `CAP_SYS_ADMIN` "to make it work".
- **`--privileged` containers** in production.
- **Disabling SELinux/AppArmor** instead of learning the denial.
- **Fixing SELinux with `chmod 777`.**
- **Forgetting `restorecon` after moving files into a web root.**
- **Assuming the container's root is harmless** without user namespaces and dropped caps.
- **Not checking the audit log** when "Permission denied" persists.

## Exercise

1. On a Linux host, run `grep Cap /proc/self/status` as a normal user and as root (`sudo`), decode both with the decoder, and explain the difference. Repeat inside a default Docker container.
2. Give a Go or Python web server access to port 443 as an unprivileged user using (a) `setcap`, (b) a systemd unit with ambient capabilities; verify with `ss -tlnp`.
3. On an SELinux system, move a file into `/var/www/html` and make nginx fail to read it; diagnose with `ausearch` and fix with `restorecon`.
4. Add a rule to the decoder's `DANGEROUS` list for `CAP_AUDIT_CONTROL` with a justification, plus a test.
