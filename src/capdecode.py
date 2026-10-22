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
