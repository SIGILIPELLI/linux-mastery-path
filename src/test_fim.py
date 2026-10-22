import os, fim
def make(tmp_path):
    r = tmp_path / "etc"; (r / "ssh").mkdir(parents=True)
    (r / "passwd").write_text("root:x:0:0::/root:/bin/sh\n"); (r / "ssh/sshd_config").write_text("PermitRootLogin no\n")
    (r / "current").symlink_to("passwd"); os.chmod(r / "passwd", 0o644); return r
def test_no_changes(tmp_path):
    r = make(tmp_path); base = fim.scan(r); assert fim.compare(base, fim.scan(r)) == []
def test_modified(tmp_path):
    r = make(tmp_path); base = fim.scan(r); (r / "ssh/sshd_config").write_text("PermitRootLogin yes\n")
    assert fim.compare(base, fim.scan(r)) == [("MODIFIED", "ssh/sshd_config", "content hash changed")]
def test_added_and_removed(tmp_path):
    r = make(tmp_path); base = fim.scan(r); (r / "backdoor.sh").write_text("#!/bin/sh\n"); (r / "passwd").unlink()
    kinds = {(k, p) for k, p, _ in fim.compare(base, fim.scan(r))}; assert ("ADDED", "backdoor.sh") in kinds and ("REMOVED", "passwd") in kinds
def test_permission_change(tmp_path):
    r = make(tmp_path); base = fim.scan(r); os.chmod(r / "passwd", 0o666)
    assert ("PERMS", "passwd", "0644 -> 0666") in fim.compare(base, fim.scan(r))
def test_symlink_retarget(tmp_path):
    r = make(tmp_path); base = fim.scan(r); (r / "current").unlink(); (r / "current").symlink_to("ssh/sshd_config")
    assert any(k == "MODIFIED" and "symlink target" in d for k, _, d in fim.compare(base, fim.scan(r)))
def test_same_size_content_change_detected(tmp_path):
    r = make(tmp_path); base = fim.scan(r); p = r / "passwd"; st = p.stat()
    p.write_text("toor:x:0:0::/root:/bin/sh\n"); os.utime(p, (st.st_atime, st.st_mtime))      # same length, same mtime
    assert [k for k, _, _ in fim.compare(base, fim.scan(r))] == ["MODIFIED"]
def test_exclude_dirs(tmp_path):
    r = make(tmp_path); (r / "cache").mkdir(); (r / "cache/x").write_text("1"); assert "cache/x" not in fim.scan(r, exclude=("cache",))
