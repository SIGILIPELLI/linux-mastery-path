import copy, yaml
from runbook_check import check
BASE = yaml.safe_load(open("runbook.yml"))
def mutated(fn):
    d = copy.deepcopy(BASE); fn(d); return check(d)
def has(p, s): return any(s in x for x in p)
def test_base_is_clean(): assert check(BASE) == []
def test_missing_owner(): assert has(mutated(lambda d: d.pop("owner")), "'owner'")
def test_alert_unknown_runbook(): assert has(mutated(lambda d: d["alerts"][0].update(runbook="nope")), "unknown runbook")
def test_orphan_runbook(): assert has(mutated(lambda d: d["alerts"].pop()), "no alert links")
def test_bad_severity(): assert has(mutated(lambda d: d["alerts"][0].update(severity="URGENT")), "severity")
def test_check_without_expectation(): assert has(mutated(lambda d: d["runbooks"]["disk-filling"]["first_checks"][0].pop("expect")), "no 'expect'")
def test_destructive_in_checks(): assert has(mutated(lambda d: d["runbooks"]["disk-filling"]["first_checks"].append({"cmd": "rm -rf /var/log/*", "expect": "x"})), "read-only")
def test_mitigation_without_undo(): assert has(mutated(lambda d: d["runbooks"]["high-error-rate"]["mitigations"][0].pop("undo")), "'undo'")
def test_destructive_mitigation_must_be_high_risk():
    assert has(mutated(lambda d: d["runbooks"]["disk-filling"]["mitigations"].append({"action": "wipe", "cmd": "truncate -s 0 /var/log/x", "risk": "low", "undo": "none"})), "risk: high")
def test_high_risk_needs_approval():
    assert has(mutated(lambda d: d["runbooks"]["disk-filling"]["mitigations"].append({"action": "reboot", "cmd": "systemctl reboot", "risk": "high", "undo": "n/a"})), "approval")
def test_no_escalation_path(): assert has(mutated(lambda d: d["runbooks"]["high-error-rate"].pop("escalate_to")), "'escalate_to'")
