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
