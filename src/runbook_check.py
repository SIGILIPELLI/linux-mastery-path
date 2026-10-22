"""Check an operations runbook file for completeness and safety. A review aid: it checks structure and a few safety rules, not whether the commands are right."""
import re, sys, yaml
REQUIRED_SERVICE = ("service", "owner", "oncall_rotation", "slo", "dependencies", "alerts", "runbooks")
REQUIRED_RUNBOOK = ("symptom", "first_checks", "scope", "mitigations", "escalate_if", "escalate_to", "verify", "after")
DESTRUCTIVE = re.compile(r"\brm\s+-rf\b|\bmkfs\b|\bdd\s+if=|\bDROP\s+(TABLE|DATABASE)\b|\bdelete\s+from\b|\btruncate\b|\bshutdown\b|\breboot\b|\bkill\s+-9\b|>\s*/dev/sd", re.I)
SEVERITIES = {"SEV1", "SEV2", "SEV3", "SEV4"}

def check(doc):
    problems = []
    for k in REQUIRED_SERVICE:
        if k not in doc: problems.append(f"missing top-level field '{k}'")
    rbs = doc.get("runbooks", {})
    names = set(rbs)
    for a in doc.get("alerts", []):
        if a.get("severity") not in SEVERITIES: problems.append(f"alert {a.get('name')}: severity must be one of {sorted(SEVERITIES)}")
        if not a.get("detection"): problems.append(f"alert {a.get('name')}: no detection condition")
        if a.get("runbook") not in names: problems.append(f"alert {a.get('name')}: references unknown runbook {a.get('runbook')!r}")
    linked = {a.get("runbook") for a in doc.get("alerts", [])}
    for n in names - linked: problems.append(f"runbook {n}: no alert links to it")
    for n, rb in rbs.items():
        for k in REQUIRED_RUNBOOK:
            if not rb.get(k): problems.append(f"runbook {n}: missing '{k}'")
        for c in rb.get("first_checks", []):
            if not c.get("expect"): problems.append(f"runbook {n}: check {c.get('cmd')!r} has no 'expect' (what does good/bad look like?)")
            if DESTRUCTIVE.search(c.get("cmd", "")): problems.append(f"runbook {n}: first_checks must be read-only, found {c['cmd']!r}")
        for m in rb.get("mitigations", []):
            for f in ("action", "cmd", "risk", "undo"):
                if not m.get(f): problems.append(f"runbook {n}: mitigation {m.get('action')!r} missing '{f}'")
            if m.get("risk") not in ("low", "medium", "high"): problems.append(f"runbook {n}: mitigation {m.get('action')!r} has invalid risk {m.get('risk')!r}")
            if DESTRUCTIVE.search(m.get("cmd", "")) and m.get("risk") != "high": problems.append(f"runbook {n}: destructive command {m['cmd']!r} must be marked risk: high")
            if m.get("risk") == "high" and "approval" not in m: problems.append(f"runbook {n}: high-risk mitigation {m.get('action')!r} needs an 'approval' field")
        if len(rb.get("first_checks", [])) < 2: problems.append(f"runbook {n}: fewer than two diagnostic checks")
    return problems

if __name__ == "__main__":
    p = check(yaml.safe_load(open(sys.argv[1]))); print("\n".join(p) if p else "OK"); sys.exit(1 if p else 0)
