---
description: "Configuration management: idempotence, desired state, check mode and drift, shown with a tested mini ensure library and how tools map onto it."
---

# 03 · Automation & Configuration Management

Servers configured by hand drift: nobody remembers which package was installed on which machine, which sysctl was changed during an incident, which file was edited in place. **Configuration management** replaces that with a description of the desired state that a tool applies repeatedly. The ideas (idempotence, convergence, check mode, drift
detection) matter more than any one tool, so this lesson implements them in about 60 lines.

!!! note "What was run"
    The mini library and its **7 pytest tests were run on macOS** against temporary directories; they model the *behaviour* of tools like Ansible. I did not run Ansible, Puppet, Chef, Salt or Terraform (no managed hosts, and the Ansible course in this series isn't built yet). Tool descriptions are general knowledge and should be checked against their current documentation. See Level 1 · Lesson 01.

## The core concepts

- **Declarative desired state**: "this directory exists with mode 0750; this file has this content" rather than "run these commands".
- **Idempotence**: applying the same configuration twice has the same result as applying it once; the second run changes nothing. This is the property that makes automation safe to re-run, schedule and retry.
- **Convergence**: whatever the starting state, applying the configuration moves the system to the desired state.
- **Check (dry-run) mode**: report what *would* change without changing it; essential before touching production.
- **Drift**: the difference between desired and actual state caused by manual edits, partial failures, or software that rewrites its own configuration. Re-applying (or just checking) detects and repairs it.
- **Orchestration vs configuration**: ordering work across many hosts (rolling restarts) is a different concern from describing one host's state.

## An idempotent "ensure" library (run)

```python
"""A miniature configuration-management library: declarative 'ensure' operations that are idempotent and report whether they changed anything.
Each function returns 'changed' or 'ok'. Supports check mode (dry run). Not a replacement for Ansible/Puppet; it shows the core idea."""
import os, stat, tempfile
from pathlib import Path

class Run:
    def __init__(self, check=False): self.check, self.log = check, []
    def record(self, what, status): self.log.append((what, status)); return status
    def summary(self):
        changed = sum(1 for _, s in self.log if s == "changed"); return f"{len(self.log)} tasks, {changed} changed, {len(self.log) - changed} ok"

def ensure_dir(run, path, mode=0o755):
    p = Path(path); status = "ok"
    if not p.is_dir(): status = "changed"; None if run.check else p.mkdir(parents=True)
    if p.is_dir() and stat.S_IMODE(p.stat().st_mode) != mode:
        status = "changed"; None if run.check else os.chmod(p, mode)
    return run.record(f"dir {path}", status)

def ensure_line(run, path, line):
    p = Path(path); lines = p.read_text().splitlines() if p.exists() else []
    if line in lines: return run.record(f"line in {path}", "ok")
    if not run.check: p.write_text("\n".join(lines + [line]) + "\n")
    return run.record(f"line in {path}", "changed")

def ensure_file(run, path, content, mode=0o644):
    """Replace a file atomically only when content or mode differ."""
    p = Path(path); same = p.exists() and p.read_text() == content and stat.S_IMODE(p.stat().st_mode) == mode
    if same: return run.record(f"file {path}", "ok")
    if not run.check:
        fd, tmp = tempfile.mkstemp(dir=p.parent); os.write(fd, content.encode()); os.close(fd); os.chmod(tmp, mode); os.replace(tmp, p)
    return run.record(f"file {path}", "changed")

def ensure_symlink(run, link, target):
    l = Path(link)
    if l.is_symlink() and os.readlink(l) == str(target): return run.record(f"symlink {link}", "ok")
    if not run.check:
        if l.is_symlink() or l.exists(): l.unlink()
        l.symlink_to(target)
    return run.record(f"symlink {link}", "changed")

def converge(run, root):
    ensure_dir(run, f"{root}/etc/myapp"); ensure_dir(run, f"{root}/var/lib/myapp", 0o750)
    ensure_file(run, f"{root}/etc/myapp/app.conf", "port=8080\nworkers=4\n", 0o640)
    ensure_line(run, f"{root}/etc/hosts", "10.0.0.5 db.internal")
    ensure_symlink(run, f"{root}/etc/myapp/current", f"{root}/var/lib/myapp")
    return run
```

Each task *inspects first, then acts only if needed*, and reports `ok` or `changed`. Running the converge function against an empty directory tree, three ways (the code printing this was a short driver using the library above):

```text
check mode (dry run)   5 tasks, 5 changed, 0 ok          ← nothing was created: the tests assert the tree does not exist afterwards
first apply            5 tasks, 5 changed, 0 ok
second apply           5 tasks, 0 changed, 5 ok          ← idempotent: nothing to do
after manual drift     5 tasks, 2 changed, 3 ok  changed: ['dir <root>/var/lib/myapp', 'file <root>/etc/myapp/app.conf']
```

For the last line I deliberately `chmod 777`'d a directory and overwrote the config file; the next run restored exactly those two and left the other three alone. The pytest suite (7 tests) also checks that a line is not appended repeatedly (three applies produce one entry), that a retargeted symlink is repaired, and that the atomic file replace leaves no temp files behind.

Design points worth stealing:

1. **Compare before change.** `ensure_file` reads the current content and mode and only writes when they differ, so mtime and inode stay stable on no-op runs (which also avoids needless service restarts).
2. **Atomic writes**: write a temp file in the same directory and `os.replace` it, so readers never see a half-written config (Lesson 02, Level 3 · 05).
3. **Check mode shares the code path**: one `if not run.check` guard around the action keeps the dry run honest, because the same comparison logic decides what would change.
4. **Return values** (`changed`/`ok`) let a higher level trigger handlers: reload nginx only if its config changed.

## How the real tools relate

| Tool/approach | Style | Notes |
|---|---|---|
| **Ansible** | Agentless (SSH), YAML playbooks of modules; each module is an idempotent "ensure" like the ones above | Easy start; see the Ansible Mastery Path in this series (not built when this was written) for the details |
| **Puppet / Chef / Salt** | Agent-based, pull, continuously converging | Strong for large fleets, more infrastructure |
| **Terraform / OpenTofu** | Declarative *infrastructure* (VMs, networks, DNS) with a state file | the [Terraform Mastery Path](https://sigilipelli.github.io/terraform-mastery-path/); different layer than host config |
| **Cloud-init / user-data** | First-boot configuration for cloud images | Good for bootstrapping, then hand over to something else |
| **Immutable images** (Packer, container images) | Build a complete image once; replace servers instead of changing them | No drift by construction, but you need the build pipeline |
| **NixOS / GitOps** | Entire system declared in code; changes via Git | Powerful, steeper learning curve |

Choosing: for a handful of long-lived servers, Ansible plus Git is a good fit; for stateless services, prefer immutable images/containers and treat servers as cattle; for infrastructure, Terraform. Mixing is normal (Terraform creates VMs, cloud-init or Ansible configures them, containers run the application).

## Practices that make automation trustworthy

1. **Everything in Git**: configs, playbooks, scripts; review changes like code.
2. **Run in check mode first**, and diff the result.
3. **Make every task idempotent**, and avoid tasks that always report "changed" (shell commands without `creates`/`when` guards), because they make drift undetectable.
4. **Separate data from logic**: variables per environment (dev/staging/prod); no secrets in Git (use a vault/secret manager; Level 2 of the DevOps-oriented courses).
5. **Test**: lint, run against a disposable VM or container, and verify idempotence by running the playbook twice and requiring zero changes on the second run (the pytest test above does the equivalent).
6. **Roll out gradually**: one host, then a batch, then the fleet, with health checks between batches.
7. **Detect drift continuously**: scheduled check-mode runs that alert on differences.
8. **Avoid snowflakes**: when a one-off manual fix is unavoidable, codify it afterwards or record it.
9. **Handle ordering and handlers**: restart a service only when its config changed, and validate config before reloading (`nginx -t`, `sshd -t`).

## How It Actually Works

A configuration-management run is: gather facts about the host (OS, packages, files), evaluate each task's *current state* against its *desired state*, perform the minimal action when they differ, and report results. Idempotence is a property of each task's implementation, not a magic of the tool: the `package` module checks the package database before installing; the `file`
module compares attributes; a raw `command` module cannot know whether it needs to run, which is why tools ask you to supply a guard. Pull-based agents repeat this every few minutes, giving continuous convergence; push-based tools do it on demand. The state of a Terraform deployment is stored in a state file recording what it created, so it can compute a diff (plan) between desired and
recorded state, and then reconcile with reality.

## Common mistakes

- **Tasks that always say "changed"** (shell commands without guards) so real changes are invisible.
- **Editing servers by hand** after automating them.
- **Putting secrets in repositories.**
- **Applying to the whole fleet at once** with no canary.
- **No check mode** or never reading the diff.
- **Restarting services on every run** instead of on config change.
- **Treating configuration management as backup or deployment** (it's neither).
- **Overusing templates for huge files** you could ship as-is, hiding what's applied.

## Exercise

1. Add `ensure_package` (shell out to a package manager on Linux, or fake the "installed" set in tests) and `ensure_service`, with tests proving idempotence.
2. Add a "handler" mechanism: tasks that report `changed` queue a restart, executed once at the end; test it with a fake service.
3. Write the equivalent of `converge` as an Ansible playbook and verify, with `--check --diff`, then a second run reporting zero changes.
4. Introduce drift in five different ways on a test VM and show your automation detecting each (check mode) and repairing each.
