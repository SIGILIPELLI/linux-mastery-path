import harden
from harden import check_sshd, check_sysctl, sshd_effective

def sev(findings, needle): return [s for s, m in findings if needle in m]

def test_defaults_alone_are_not_enough():
    f = check_sshd("")                               # empty config = documented defaults
    assert "HIGH" in sev(f, "PasswordAuthentication")
    assert sev(f, "PermitRootLogin") == ["HIGH"]     # the default is prohibit-password; the baseline wants an explicit 'no'

def test_hardened_sshd_clean():
    cfg = "PermitRootLogin no\nPasswordAuthentication no\nKbdInteractiveAuthentication no\nAllowGroups ssh-users\nMaxAuthTries 3\nLoginGraceTime 30\n"
    assert check_sshd(cfg) == []

def test_first_value_wins():
    assert sshd_effective("PermitRootLogin no\nPermitRootLogin yes\n")["permitrootlogin"] == "no"

def test_match_block_not_applied_globally():
    cfg = "PasswordAuthentication no\nMatch User legacy\n    PasswordAuthentication yes\n"
    assert sshd_effective(cfg)["passwordauthentication"] == "no"

def test_comments_and_case():
    assert sshd_effective("permitrootlogin NO # allow nothing\n")["permitrootlogin"] == "no"

def test_sysctl_missing_and_wrong():
    f = check_sysctl("net.ipv4.tcp_syncookies = 0\nkernel.randomize_va_space=2\n")
    assert sev(f, "tcp_syncookies") == ["MEDIUM"] and not sev(f, "randomize_va_space") and sev(f, "rp_filter") == ["LOW"]

def test_run_sorts_high_first():
    f = harden.run(sshd="PasswordAuthentication yes\n", sysctl="")
    assert f[0][0] == "HIGH" and f[-1][0] == "LOW"

def test_integrates_fstab_and_unit_linters():
    f = harden.run(fstab="/dev/sdb1 /srv ext4 defaults 0 2\n", units=[("bad.service", "[Service]\nExecStart=app\n")])
    assert any("fstab:" in m for _, m in f) and any("unit bad.service:" in m for _, m in f)
