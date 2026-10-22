---
description: "SSH keys inspected for real, key permissions, authorized_keys options, ssh -G and known_hosts, and sshd hardening with documented defaults."
---

# 08 · SSH: Keys, Config & Hardening

SSH is how you reach nearly every Linux server, which makes it both your most important tool and the most attacked service on the internet. Three habits solve most of the problems: **use keys (not passwords), keep your client config tidy, and lock the server down.**

!!! note "What was run"
    The client-side commands (`ssh-keygen`, `ssh -G`, `ssh-keygen -lf`, `-H`, `-F`) were **run on macOS** with a throwaway key pair in a temp directory and nothing was connected to any real server. Server configuration (`sshd_config`) was **not run**:
    option names and defaults come from the `sshd_config(5)` man page (man7.org, October 2026). OpenSSH versions and distribution defaults differ. See Level 1 · Lesson 01.

## Keys instead of passwords

A key pair is a **private key** (stays on your machine, never shared) and a **public key** (installed on servers). Authentication proves you hold the private key without sending it.

```bash
ssh-keygen -t ed25519 -C "alice@laptop" -f ~/.ssh/id_ed25519     # modern default; ask for a passphrase
ssh-copy-id -i ~/.ssh/id_ed25519.pub alice@server                  # appends the public key to ~/.ssh/authorized_keys
ssh -i ~/.ssh/id_ed25519 alice@server
```

Run (throwaway keys in a temp directory):

```text
ssh-keygen -q -t ed25519 -N '' -C demo@lab -f k1       → files k1 (-rw-------) and k1.pub (-rw-r--r--)
ssh-keygen -lf k1.pub    → 256 SHA256:<fingerprint> demo@lab (ED25519)
ssh-keygen -q -t rsa -b 3072 -N '' -f k2 ; ssh-keygen -lf k2.pub → 3072 SHA256:<fingerprint> ... (RSA)
```

`ssh-keygen` created the private key with mode **`-rw-------` (0600)** automatically. An Ed25519 public key is short (one line, 256-bit); RSA at 3072 bits is longer. The **fingerprint** (a SHA-256 hash of the public key) is how you verify
a key out of band. Ed25519 is the usual recommendation today; RSA with at least 3072 bits remains widely compatible. Use a passphrase on keys that live on laptops and an agent (`ssh-agent`, `ssh-add`) so you type it once.

### Permissions matter

OpenSSH refuses keys that are readable by others. When I made the private key world-readable (`chmod 644 k1`) and attempted to use it, the client printed a warning about unprotected key file permissions
instead of using it (in my test the TCP connection to localhost was refused first, so I did not capture that warning; the rule is documented in `ssh(1)` and well known). The expected modes:

| Path | Mode |
|---|---|
| `~/.ssh` | `700` |
| private keys | `600` |
| `~/.ssh/authorized_keys`, `config` | `600` (or at most `644` for authorized_keys on some setups) |
| Home directory | not group- or world-writable |

On the server side, `sshd` with default `StrictModes yes` rejects authentication if the user's home, `.ssh` or `authorized_keys` are writable by others; a very common reason keys "don't work".

## authorized_keys and restricting keys

Each line of `~/.ssh/authorized_keys` is a public key, optionally prefixed with **options**:

```text
command="/usr/local/bin/backup-only",no-pty,no-port-forwarding,no-agent-forwarding,from="203.0.113.0/24" ssh-ed25519 AAAA... backup@host
```

That key can only run one command, from one network, with no shell, forwarding or agent. I tested that `ssh-keygen -l -f` parses such a line (it reported the key's fingerprint, ignoring the options), but I could not test the restrictions without a server. Restricted keys are the right way to
give automation (backups, deploys) the least power it needs. Keep a record of who owns each key (the comment field) and remove keys when people leave.

## Client config: ~/.ssh/config

```text
Host prod-*
    User deploy
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
    ServerAliveInterval 30

Host bastion
    HostName bastion.example.com
    User alice

Host prod-db
    HostName 10.0.2.15
    ProxyJump bastion
```

`ssh prod-db` now hops through the bastion automatically (`ProxyJump`). To see **what configuration will actually be used**, ask the client: `ssh -G host` prints the resolved options. Run with options given on the command line:

```text
$ ssh -G -o HostName=example.invalid -o User=deploy -o Port=2222 -o IdentityFile=~/k1 myhost | grep -E "^(user|hostname|port|identityfile|stricthostkeychecking|passwordauthentication|pubkeyauthentication|serveraliveinterval) "
user deploy
hostname example.invalid
port 2222
passwordauthentication yes
pubkeyauthentication true
stricthostkeychecking ask
serveraliveinterval 0
identityfile ~/k1
```

`-G` expands every default too: on this client `stricthostkeychecking ask`, `passwordauthentication yes` and `serveraliveinterval 0`. First-match-wins: for each option the **first** value found (command line, then your config in file order, then system
config) is used, so put specific `Host` blocks before `Host *`.

## known_hosts: trusting the server

The first time you connect, SSH shows the server's key fingerprint and asks you to trust it, then records it in `~/.ssh/known_hosts`. On later connections, a **changed** key triggers the loud "REMOTE HOST IDENTIFICATION HAS CHANGED" warning (a rebuilt server, or an attack).
Verify fingerprints out of band for sensitive hosts. `ssh-keygen -H` hashes hostnames in the file (run: the entry for `example.invalid` became `|1|<salt>|<hash>`, so a stolen file doesn't list your servers) and `ssh-keygen -F host` still finds an entry (exit status 0 in my test); `ssh-keygen -R host` removes one after a legitimate rebuild.

## Hardening sshd

Server settings live in `/etc/ssh/sshd_config` and `/etc/ssh/sshd_config.d/*.conf`. Per `sshd_config(5)`, relevant documented defaults and recommendations:

| Option | Default (per man page) | Recommended for servers |
|---|---|---|
| `PermitRootLogin` | `prohibit-password` | `no` (log in as a user, then `sudo`) |
| `PasswordAuthentication` | `yes` | `no` once keys work |
| `KbdInteractiveAuthentication` | `yes` | `no` if you don't use it (it can be another password path) |
| `PubkeyAuthentication` | `yes` | `yes` |
| `PermitEmptyPasswords` | `no` | `no` |
| `MaxAuthTries` | `6` | `3` |
| `LoginGraceTime` | `120` seconds | `30` |
| `X11Forwarding` | `no` | `no` unless needed |
| `AllowUsers` / `AllowGroups` | all users allowed | limit to named users/groups |
| `ClientAliveInterval` | `0` (disabled) | e.g. `300` with `ClientAliveCountMax 2` to drop dead sessions |

```text
# /etc/ssh/sshd_config.d/10-hardening.conf
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
AllowGroups ssh-users
MaxAuthTries 3
LoginGraceTime 30
```

**Always validate and keep a session open**: `sudo sshd -t` checks syntax (and `sshd -T` prints the effective configuration); reload with `systemctl reload ssh` (the unit is `ssh` on Debian family, `sshd` on RHEL family); open a **second terminal** to test the new
settings before closing the first (Lesson 07's lock-out warning applies). Changing the port (security by obscurity) reduces log noise but not risk; keys, no passwords, no root login, and firewall allowlists are what matter. Fail2ban or `MaxStartups` rate limits reduce brute-force load.

Agent forwarding (`-A`) and port forwarding are powerful and risky: a compromised intermediate host can use your forwarded agent. Prefer `ProxyJump`. SSH certificates (signed keys with expiry) scale better than copying keys to many hosts; mentioned for awareness, not run.

## How It Actually Works

An SSH connection first negotiates algorithms and performs a key exchange (Diffie-Hellman variants) that establishes a shared session key; the server proves its identity by signing with its **host key** (what `known_hosts` records), so you know you're talking to the right machine. Then
user authentication: with public keys, the server sends a challenge that only the private-key holder can sign; the server checks the signature against `authorized_keys`. Everything after is encrypted and integrity-protected. Sessions carry multiple **channels**: your shell, port forwards,
file transfers (`scp`/`sftp`) over the same connection. The server's listening process forks a child per connection which, after authentication, switches to your UID (Level 1 · 05) and runs your shell or the forced command.

## Common mistakes

- **Leaving password authentication on** for an internet-facing server.
- **Private key permissions too open**, or home directory writable by group (server-side `StrictModes`).
- **Copying private keys between machines** instead of generating one per device.
- **Agent forwarding to untrusted hosts.**
- **Ignoring changed host key warnings** (`StrictHostKeyChecking no` everywhere).
- **Editing `sshd_config` and reloading without a second session** or `sshd -t`.
- **Shared accounts/keys** that destroy accountability.
- **Never rotating or removing old authorized keys.**

## Exercise

1. Generate an Ed25519 key with a passphrase, load it into `ssh-agent`, and inspect the fingerprint. Compare the length and fingerprint line for a 4096-bit RSA key.
2. Write a `~/.ssh/config` with a bastion and an internal host using `ProxyJump`; check it with `ssh -G internal`.
3. On a Linux VM, apply the hardening snippet; verify with `sshd -T | grep -E "permitrootlogin|passwordauthentication"` and from a second terminal that a password login now fails while a key login works.
4. Create a restricted key that can only run `uptime`; prove from a client that a shell attempt is refused.
