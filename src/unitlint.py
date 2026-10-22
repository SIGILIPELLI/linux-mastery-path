"""Lint a systemd .service unit file for common mistakes. Static checks only: not a replacement for `systemd-analyze verify`."""
import configparser, os, re, sys

def parse(text):
    cp = configparser.ConfigParser(strict=False, interpolation=None, delimiters=("=",))
    cp.optionxform = str                                   # keys are case-sensitive in unit files
    cp.read_string(text)
    return cp

def lint(text):
    problems = []
    cp = parse(text)
    for sec in ("Unit", "Service", "Install"):
        if sec not in cp: problems.append(f"missing [{sec}] section")
    svc = cp["Service"] if "Service" in cp else {}
    install = cp["Install"] if "Install" in cp else {}
    stype = svc.get("Type", "simple")
    exec_start = svc.get("ExecStart", "")
    if not exec_start and stype != "oneshot": problems.append("no ExecStart= (required unless Type=oneshot)")
    if exec_start:
        prog = exec_start.lstrip("-@+!:").split()[0] if exec_start.split() else ""
        if not prog.startswith("/"): problems.append(f"ExecStart= must start with an absolute path, got {prog!r}")
        if re.search(r"[|;&]|>>?|<", exec_start): problems.append("ExecStart= uses shell syntax (| ; & >); systemd does not run a shell, wrap it with /bin/sh -c")
    if stype == "forking" and "PIDFile" not in svc: problems.append("Type=forking without PIDFile= (systemd may guess the main PID wrong)")
    if stype in ("simple", "exec", "notify", "forking", "idle") and svc.get("Restart") is None: problems.append("no Restart= policy (default is no restart)")
    if svc.get("Restart") == "always" and "RestartSec" not in svc: problems.append("Restart=always without RestartSec= (default 100ms can make a crash loop spin; also check StartLimit*)")
    if "User" not in svc and "DynamicUser" not in svc: problems.append("no User= or DynamicUser=: the service runs as root")
    hardening = [k for k in ("NoNewPrivileges", "ProtectSystem", "ProtectHome", "PrivateTmp", "CapabilityBoundingSet", "ReadWritePaths") if k in svc]
    if len(hardening) < 2: problems.append("little sandboxing: consider NoNewPrivileges=, ProtectSystem=, PrivateTmp=, ProtectHome=")
    if "WantedBy" not in install and "RequiredBy" not in install: problems.append("[Install] has no WantedBy=/RequiredBy=: `systemctl enable` will do nothing")
    wd = svc.get("WorkingDirectory")
    if wd and not wd.lstrip("-~").startswith(("/", "~")): problems.append(f"WorkingDirectory= should be absolute, got {wd!r}")
    return problems

if __name__ == "__main__":
    probs = lint(open(sys.argv[1]).read())
    print("\n".join(probs) if probs else "OK")
    sys.exit(1 if probs else 0)
