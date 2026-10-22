---
description: "Containers on Linux: image layers and whiteouts (modelled and tested), a Dockerfile linter, runtimes, rootless mode, limits and PID 1."
---

# 09 · Containers on Linux: Images, Runtimes & Limits

Level 3 · 06 explained that a container is a process in namespaces and cgroups. This lesson covers the other half: the **image** (a stack of filesystem layers), how runtimes assemble and start it, the limits you must set, and the mistakes that come from forgetting that "container" doesn't mean "VM".

!!! note "What was run"
    **No container runtime (Docker, Podman, containerd) was available**, so no `docker`/`podman` command was run. What was run, on macOS: a **Python model of OCI-style image layers (tar layers with whiteout files) with 6 pytest tests**, and a **Dockerfile linter with 12 pytest tests**. The layer model follows the OCI/Docker layer format as I understand it (whiteouts as `.wh.<name>` files, opaque directories as `.wh..wh..opq`)
    but is my implementation, not Docker's. Runtime behaviour descriptions are from documentation and general knowledge; check your runtime's docs. See Level 1 · Lesson 01.

## Images are stacks of layers

An image is an ordered list of **layers**, each a tar archive of filesystem changes, plus a JSON config (entrypoint, environment, user, exposed ports). Building from a Dockerfile creates one layer for each filesystem-changing instruction (`RUN`, `COPY`, `ADD`). At run time the runtime stacks the layers with a union filesystem (**overlayfs**): lower layers read-only, plus a thin writable layer on top for the container's changes. Layers are
content-addressed (by SHA-256) and shared between images, so ten images based on the same base image store that base once.

**Deleting a file in a later layer doesn't remove it from the image.** The later layer only adds a *whiteout* marker that hides the lower file; the original bytes still ship. I modelled this:

```python
"""OCI/Docker-style image layers as tar archives applied in order, with 'whiteout' files marking deletions (.wh.<name>) and
'.wh..wh..opq' marking an opaque directory. Demonstrates why deleting a file in a later layer does NOT shrink the image."""
import io, tarfile, posixpath

def make_layer(files=None, deletes=()):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as t:
        for path, data in (files or {}).items():
            ti = tarfile.TarInfo(path); ti.size = len(data); t.addfile(ti, io.BytesIO(data))
        for path in deletes:
            d, name = posixpath.split(path); ti = tarfile.TarInfo(posixpath.join(d, ".wh." + name)); ti.size = 0; t.addfile(ti, io.BytesIO(b""))
    return buf.getvalue()

def apply_layers(layers):
    fs = {}
    for blob in layers:
        with tarfile.open(fileobj=io.BytesIO(blob)) as t:
            for m in t.getmembers():
                d, name = posixpath.split(m.name)
                if name == ".wh..wh..opq":                                  # opaque dir: drop everything below it from lower layers
                    fs = {p: c for p, c in fs.items() if not p.startswith(d + "/")}
                elif name.startswith(".wh."):
                    target = posixpath.join(d, name[4:]); fs = {p: c for p, c in fs.items() if p != target and not p.startswith(target + "/")}
                elif m.isfile(): fs[m.name] = t.extractfile(m).read()
    return fs

def image_size(layers): return sum(len(b) for b in layers)
```

Results:

```text
layers: l1 = usr/bin/app (50 KB) + tmp/installer.tar (300 KB);  l2 = whiteout of tmp/installer.tar;  l3 = etc/conf
files visible: ['etc/conf', 'usr/bin/app']          ← the installer is gone from the filesystem...
layer sizes: [358400, 10240, 10240]  total image bytes: 378880      ← ...but every byte of it is still in layer 1
same final filesystem built without the installer ever stored: 61440 bytes
6 passed (pytest)
```

(The sizes include tar's block padding, so a small layer is ~10 KB.) The tests assert exactly this: a whiteout hides a file (`test_whiteout_hides_file`), but the total size does **not** shrink (`test_deleting_does_not_shrink_image`), while cleanup *inside the same `RUN`* (download, use, delete in one layer) produces a smaller image with the identical filesystem (`test_same_layer_cleanup_does_shrink`). One of my first assertions used a
fixed byte limit that tar's padding broke, and I rewrote it as a comparison between the two builds. This is why Dockerfiles chain commands with `&&` and why secrets copied in one layer and "deleted" later remain extractable from the image forever.

Practical consequences:

- **Order layers by change frequency**: put rarely changing steps (install dependencies) before frequently changing ones (copy source) so the build cache stays valid.
- **Multi-stage builds**: compile in a fat build stage, copy only the artifacts into a minimal final stage (distroless, Alpine or slim): smaller image, fewer vulnerabilities, no compilers in production.
- **Never put secrets in layers** (`ENV`, `COPY .env`, `ARG` passwords all persist in history); use build secrets (`RUN --mount=type=secret`) or runtime injection.
- **Pin base images** by version tag or, best, digest, and rebuild regularly to pick up security fixes (Lesson 05).

## A Dockerfile linter (run)

```python
"""Lint a Dockerfile for common image-quality and security problems. Static, line-based checks; not a Dockerfile parser."""
import re, sys

def logical_lines(text):
    cur = ""
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if s.endswith("\\"): cur += s[:-1] + " "; continue
        yield cur + s; cur = ""
    if cur: yield cur

def lint(text):
    problems, lines = [], list(logical_lines(text))
    froms = [l for l in lines if l.upper().startswith("FROM ")]
    if not froms: problems.append("no FROM instruction")
    for l in froms:
        img = l.split()[1]
        if img.lower() != "scratch" and (":" not in img.split("/")[-1] or img.endswith(":latest")) and "@sha256:" not in img:
            problems.append(f"{l!r}: image tag is missing or ':latest' (builds are not reproducible); pin a version or digest")
    last_stage = lines[[i for i, l in enumerate(lines) if l.upper().startswith("FROM ")][-1]:] if froms else lines
    users = [l for l in last_stage if l.upper().startswith("USER ")]
    if not users or users[-1].split()[1] in ("root", "0"): problems.append("final stage runs as root (add a non-root USER)")
    for l in lines:
        u = l.upper()
        if u.startswith("ADD ") and not re.search(r"https?://", l) and not re.search(r"\.(tar|tgz|tar\.gz|tar\.xz)\b", l): problems.append(f"{l!r}: use COPY instead of ADD for plain files")
        if re.search(r"\bapt-get\s+install\b", l) and "--no-install-recommends" not in l: problems.append(f"{l!r}: apt-get install without --no-install-recommends")
        if re.search(r"\bapt-get\s+install\b", l) and "rm -rf /var/lib/apt/lists" not in l: problems.append(f"{l!r}: apt lists not removed in the same RUN (layer keeps the cache)")
        if re.search(r"\bapt-get\s+update\b", l) and "install" not in l: problems.append(f"{l!r}: 'apt-get update' alone in a RUN layer can be cached stale; combine with install")
        if u.startswith(("ENV ", "ARG ")) and re.search(r"(PASSWORD|SECRET|TOKEN|API_?KEY)\s*[= ]\s*\S+", l, re.I): problems.append(f"{l!r}: looks like a secret baked into the image")
        if re.search(r"curl[^|]*\|\s*(sudo\s+)?(ba)?sh", l): problems.append(f"{l!r}: pipes a download into a shell")
        if u.startswith("RUN ") and re.search(r"\bsudo\b", l): problems.append(f"{l!r}: sudo inside a build is unnecessary")
    if not any(l.upper().startswith("HEALTHCHECK") for l in lines): problems.append("no HEALTHCHECK (orchestrators may provide one; mention if intentional)")
    if not any(l.upper().startswith(("ENTRYPOINT", "CMD")) for l in last_stage): problems.append("no CMD or ENTRYPOINT in the final stage")
    cmds = [l for l in last_stage if l.upper().startswith(("CMD ", "ENTRYPOINT "))]
    for l in cmds:
        if not l.split(None, 1)[1].lstrip().startswith("["): problems.append(f"{l!r}: shell form runs under /bin/sh -c, so signals may not reach the app; use exec form [\"...\"]")
    return problems

if __name__ == "__main__":
    p = lint(open(sys.argv[1]).read()); print("\n".join(p) if p else "OK"); sys.exit(1 if p else 0)
```

The 12 tests cover a good Dockerfile (clean), each rule's violation, the digest exemption, and multi-stage handling (only the final stage's `USER`/`CMD` count). Running it on a deliberately bad file:

```text
'FROM ubuntu': image tag is missing or ':latest' (builds are not reproducible); pin a version or digest
final stage runs as root (add a non-root USER)
'ADD . /app': use COPY instead of ADD for plain files
'RUN apt-get update': 'apt-get update' alone in a RUN layer can be cached stale; combine with install
'RUN apt-get install -y curl python3': apt-get install without --no-install-recommends
'RUN apt-get install -y curl python3': apt lists not removed in the same RUN (layer keeps the cache)
'ENV DB_PASSWORD=hunter2': looks like a secret baked into the image
'RUN curl -fsSL https://example.com/setup.sh | sh': pipes a download into a shell
no HEALTHCHECK (orchestrators may provide one; mention if intentional)
'CMD python3 /app/main.py': shell form runs under /bin/sh -c, so signals may not reach the app; use exec form ["..."]
```

This is a toy compared with Hadolint, which has many more rules and a real parser; use that in CI. The rules are common guidance, not a standard.

## Runtimes and rootless

Docker's architecture is a daemon (`dockerd`) that calls **containerd**, which calls a low-level OCI runtime (**runc**, or crun/gVisor/Kata for stronger isolation) to create the namespaces, cgroups and process. **Podman** is daemonless and supports rootless by default; Kubernetes talks to containerd or CRI-O. All run OCI images.

**Rootless containers** run the whole runtime as an unprivileged user using user namespaces, so even a container escape lands as an unprivileged user on the host. The cost is some features (low ports, certain networking modes need helpers). **Running as non-root inside the container** (`USER app`) and **dropping capabilities** (`--cap-drop=ALL --cap-add=...`, Level 3 · 07) are separate, complementary measures. Avoid `--privileged`, mounting
the Docker socket (it's root on the host), and `--pid=host`/`--network=host` unless you truly need them.

## Resource limits

Without limits a container may consume the whole host. Set them (they translate into cgroup files, Level 3 · 06):

```bash
docker run --memory=512m --memory-swap=512m --cpus=1.5 --pids-limit=200 --read-only --tmpfs /tmp \
           --cap-drop=ALL --security-opt no-new-privileges myimage:1.4.2          # not run
```

`--memory` sets `memory.max`: exceeding it triggers an OOM kill of the container's process with exit code **137** even when the host has free RAM. `--cpus=1.5` is a CPU *quota* (throttling, with latency effects). `--read-only` plus `tmpfs` for scratch makes the root filesystem immutable. Applications running in a container must be aware of the limits: older runtimes of Java, Go and others sized heaps or thread pools from the
host's memory and CPU count (`/proc/meminfo` and CPU counts inside containers reflect the host unless the runtime reads cgroups), causing OOM kills; modern runtimes (recent JVMs, Go 1.19 and later with GOMEMLIMIT guidance) are cgroup-aware, but verify yours.

## Signals, PID 1 and shutdown

The container's main process is PID 1 in its PID namespace. Linux gives PID 1 special signal semantics: signals with no handler installed are ignored for PID 1 (so `SIGTERM` does nothing unless the program handles it), and PID 1 is responsible for reaping orphaned children (Level 1 · 07: zombies). Consequences: use **exec form** `CMD ["app", "args"]` so your app (not a shell) is PID 1 and receives
`docker stop`'s SIGTERM; handle SIGTERM for graceful shutdown (finish requests, close connections); use `--init` (tini) if the app spawns children. `docker stop` waits a grace period (default 10 s) and then sends SIGKILL, producing exit 137 if your app didn't exit.

## Networking, storage and logging

- **Networking**: by default containers live in a network namespace connected to a bridge with NAT; `-p 8080:80` adds a DNAT rule (netfilter, Level 3 · 08). Containers on user-defined networks resolve each other by name via an embedded DNS.
- **Storage**: the writable layer is ephemeral and slower; keep data in **volumes** or bind mounts, which survive container removal. Watch for permission mismatches between container UIDs and host files (user namespaces remap them).
- **Logging**: containers should write logs to stdout/stderr; the runtime captures them (`docker logs`, the journal driver). Unbounded json-file logs fill `/var` (Lesson 06), so set `max-size` and `max-file`.
- **State**: a container is a disposable process; don't SSH in and change it, rebuild the image (Lesson 03's immutable approach).

## How It Actually Works

When you run a container, the runtime unpacks (or reuses) the image's layers, mounts them with **overlayfs** (`lowerdir` layers read-only, `upperdir` for writes, `workdir` for atomic operations); a write to a file in a lower layer triggers **copy-up** of that file into the upper layer first, which is why modifying big files in a container is slow and why the writable layer grows. The runtime then calls `clone` with namespace flags, sets up the cgroup, mounts the overlay as the
new root with `pivot_root`, applies capabilities, seccomp and LSM profiles, and `execve`s the entrypoint. Images are distributed as a manifest listing layer digests; pulling fetches only layers you lack. Because the runtime configures nothing the kernel doesn't already offer, everything the container can do is visible from the host.

## Common mistakes

- **Running as root with `--privileged`** or the Docker socket mounted.
- **No resource limits** (noisy neighbour, OOM of the host).
- **Secrets in layers/ENV.**
- **`:latest` and unpinned bases;** images never rebuilt for security fixes.
- **Shell-form CMD** (SIGTERM never reaches the app) and apps that ignore SIGTERM.
- **Writing data into the container layer.**
- **Giant images** (build tools in the final stage).
- **Treating a container as a security boundary equal to a VM.**
- **Unbounded logs.**

## Exercise

1. Take a Dockerfile you own and run the linter, then Hadolint if you can install it; fix every real finding and compare which tool found what.
2. Build two images of the same app (naive single-stage vs multi-stage) and compare sizes with `docker history`; relate each layer to the model above.
3. Run a container with `--memory=64m` that allocates 200 MB; observe exit code 137 and the cgroup's `memory.events`. Then run a signal-handling test: with shell-form and exec-form CMD, measure how long `docker stop` takes.
4. Run a container rootless (Podman) and compare `ps` on the host with the container's view; find its namespaces in `/proc/<pid>/ns`.
