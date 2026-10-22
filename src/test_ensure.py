import os, stat
from pathlib import Path
import ensure
from ensure import Run, converge

def test_first_run_changes_second_run_does_not(tmp_path):
    r1 = converge(Run(), tmp_path); assert all(s == "changed" for _, s in r1.log)
    r2 = converge(Run(), tmp_path); assert all(s == "ok" for _, s in r2.log)
def test_check_mode_changes_nothing(tmp_path):
    r = converge(Run(check=True), tmp_path)
    assert all(s == "changed" for _, s in r.log) and not (tmp_path / "etc/myapp").exists()
def test_drift_is_repaired(tmp_path):
    converge(Run(), tmp_path); conf = tmp_path / "etc/myapp/app.conf"; conf.write_text("port=9999\n")
    r = converge(Run(), tmp_path); assert ("file %s" % conf, "changed") in r.log and conf.read_text() == "port=8080\nworkers=4\n"
def test_mode_drift(tmp_path):
    converge(Run(), tmp_path); os.chmod(tmp_path / "var/lib/myapp", 0o777)
    r = converge(Run(), tmp_path); assert stat.S_IMODE((tmp_path / "var/lib/myapp").stat().st_mode) == 0o750 and "1 changed" in r.summary()
def test_line_not_duplicated(tmp_path):
    for _ in range(3): converge(Run(), tmp_path)
    assert (tmp_path / "etc/hosts").read_text().count("db.internal") == 1
def test_symlink_retargeted(tmp_path):
    converge(Run(), tmp_path); link = tmp_path / "etc/myapp/current"; link.unlink(); link.symlink_to("/tmp")
    r = converge(Run(), tmp_path); assert os.readlink(link) == str(tmp_path / "var/lib/myapp") and "1 changed" in r.summary()
def test_atomic_replace_leaves_no_temp(tmp_path):
    converge(Run(), tmp_path); (tmp_path / "etc/myapp/app.conf").write_text("x"); converge(Run(), tmp_path)
    assert sorted(p.name for p in (tmp_path / "etc/myapp").iterdir()) == ["app.conf", "current"]
