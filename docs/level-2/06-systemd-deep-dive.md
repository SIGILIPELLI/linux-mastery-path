---
description: "systemd units, targets, and the dependency graph explained through a real service's unit file and its full dependency tree."
---

# 06 · systemd Deep Dive: Units, Targets & Dependencies

`systemctl status` and `systemctl restart` get most people through a normal day, but "why won't this service
start," "what is it actually waiting on," and "what does `multi-user.target` even mean" all need the model
underneath those two commands: units, targets, and the dependency graph systemd resolves to decide what starts,
in what order, and when.

## Units and targets

A **unit** is systemd's generic word for "a thing it manages" — a `.service` (a daemon or one-shot command), a
`.mount` (a filesystem mount point), a `.socket` (a listening socket, which can start its service lazily on first
connection), a `.timer` (Lesson 7's scheduled-trigger mechanism), and several other types. A **target** is a
special unit that exists purely to group other units as a synchronization point — `multi-user.target` doesn't "do"
anything itself; it's the named milestone that "normal multi-user operation is ready" maps onto, and other units
declare `WantedBy=multi-user.target` to say "start me as part of reaching that milestone," which is the mechanism
behind `systemctl enable`.

## Worked example: a real unit file and its real dependency tree

```text
$ systemctl get-default
graphical.target

$ systemctl cat ssh.service
# /usr/lib/systemd/system/ssh.service
[Unit]
Description=OpenBSD Secure Shell server
Documentation=man:sshd(8) man:sshd_config(5)
After=network.target nss-user-lookup.target auditd.service
ConditionPathExists=!/etc/ssh/sshd_not_to_be_run

[Service]
ExecStartPre=/usr/sbin/sshd -t
ExecStart=/usr/sbin/sshd -D $SSHD_OPTS
ExecReload=/usr/sbin/sshd -t
ExecReload=/bin/kill -HUP $MAINPID
KillMode=process
Restart=on-failure
Type=notify

[Install]
WantedBy=multi-user.target
Alias=sshd.service

$ systemctl list-dependencies ssh.service --no-pager | head -n8
ssh.service
● ├─-.mount
● ├─ssh.socket
○ ├─sshd-keygen.service
● ├─system.slice
● └─sysinit.target
●   ├─apparmor.service
●   ├─blk-availability.service
```

(Real output from this course's lab VM.) The `[Unit]` section's `After=` line is an **ordering** constraint, not
a dependency by itself: it says "if both of us are going to run, start network-related units first," but says
nothing about whether `ssh.service` actually *needs* them — that's what `Wants=`/`Requires=` (not present here,
because SSH is deliberately tolerant of starting without a fully-ready network) would express. `ConditionPathExists=!...`
is a runtime gate that can skip starting the unit entirely without that counting as a failure. `[Install]`'s
`WantedBy=multi-user.target` is the line `systemctl enable` acts on: enabling creates a symlink so that reaching
`multi-user.target` pulls this service in. `list-dependencies` walks the *actual* resolved graph for this unit —
notice `ssh.socket` appears (systemd's socket-activation companion unit) and `sysinit.target` pulls in a long list
of early-boot units this service transitively depends on reaching first.

## How It Actually Works

systemd starts units **in parallel** wherever the dependency graph allows it, which is the single biggest reason
it boots faster than older sequential init systems — if two units have no ordering relationship to each other,
there's no reason to make one wait for the other. `After=`/`Before=` express pure ordering; `Wants=`/`Requires=`
express the actual pull-in relationship (whether reaching the target should bring the other unit along at all),
and `Requires=` additionally propagates failure (if a strictly required unit fails, the dependent unit is stopped
too) while `Wants=` doesn't. systemd computes a full directed graph from all of this across every loaded unit and
runs a topological-ish parallel scheduler over it — which is also exactly why a cyclic dependency (A `Requires=`
B, B `Requires=` A) is a real, specific failure systemd detects and reports, rather than something that just
hangs silently.

`Type=` in `[Service]` tells systemd **how to know the service actually finished starting**, which is more subtle
than "the process exists." `Type=simple` (the default) considers the service started the instant `ExecStart`'s
process is forked — fine for a process that's immediately ready, wrong for one with real startup work to do.
`Type=notify` (used by `ssh.service` above) requires the program to explicitly call `sd_notify(READY=1)` via the
systemd notification protocol once it's genuinely ready to serve, which is why services using it can be relied on
not to have clients connect to them a half-second too early — something `Type=simple` can't guarantee at all.

## Common mistakes

- **Treating `After=` as if it implies a dependency.** As shown above, it's pure ordering — a unit can be ordered
  `After=` something that never even runs, and will still start fine (just without waiting for it, since it never
  appears).
- **Editing a vendor-shipped unit file directly under `/usr/lib/systemd/system/`.** Package updates overwrite it
  (the same fragility as `grub.cfg` and files under `/usr`, Level 1); the correct approach is `systemctl edit
  <unit>`, which creates an override file under `/etc/systemd/system/<unit>.d/` that survives upgrades.
- **Forgetting `systemctl daemon-reload` after hand-editing a unit file.** systemd caches parsed unit definitions;
  without a reload, `systemctl restart` on the changed unit will apply the *old* configuration, which looks exactly
  like the edit "didn't work."

## Exercise

Pick any running service on a Linux system you control and run `systemctl cat <service>` followed by
`systemctl list-dependencies <service>`. Identify one `After=` relationship and one `Wants=`/`Requires=`
relationship in its unit file (or its drop-ins, if it has none directly), and explain in your own words what would
actually change in startup behavior if each were removed.
