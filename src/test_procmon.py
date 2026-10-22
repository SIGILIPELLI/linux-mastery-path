import procmon, make_fixture
def snap(tmp_path, interval=0.0, **kw):
    make_fixture.build(tmp_path, **kw); return procmon.snapshot(str(tmp_path))
def msgs(s, **kw): return [m for _, m in procmon.alerts(s, **kw)]

def test_healthy_has_no_alerts(tmp_path):
    s = snap(tmp_path); assert s["cpus"] == 4 and abs(s["mem_available_pct"] - 75.0) < 0.01 and procmon.alerts(s) == []
def test_top_rss_sorted(tmp_path):
    s = snap(tmp_path); assert [p["name"] for p in s["top_rss"]] == ["java", "systemd", "sshd"]
def test_high_load(tmp_path):
    s = snap(tmp_path, load="7.00 5.00 3.00 9/400 1"); assert any("CRIT" == sev for sev, _ in procmon.alerts(s))
def test_low_memory_and_swap(tmp_path):
    s = snap(tmp_path, mem_avail=1000000, swap_free=1000000); m = msgs(s); assert any("memory available" in x for x in m) and any("swap in use" in x for x in m)
def test_zombie_detected(tmp_path):
    s = snap(tmp_path, procs=[(1, "init", "S", 100, 3), (77, "defunct", "Z", 0, 0)]); assert s["zombies"] == [77] and any("zombie" in x for x in msgs(s))
def test_many_fds(tmp_path):
    s = snap(tmp_path, procs=[(1, "init", "S", 100, 3), (9, "leaky", "S", 100, 900)]); assert any("open files" in x for x in msgs(s))
def test_cpu_percent_between_samples(tmp_path):
    make_fixture.build(tmp_path)
    calls = []
    def sleeper(_):
        (tmp_path / "stat").write_text("cpu  1300 0 600 8500 150 0 0 0\ncpu0 1 0 0 1 0 0 0 0\ncpu1 1 0 0 1 0 0 0 0\ncpu2 1 0 0 1 0 0 0 0\ncpu3 1 0 0 1 0 0 0 0\n"); calls.append(1)
    s = procmon.snapshot(str(tmp_path), interval=1.0, sleeper=sleeper)
    assert calls and abs(s["cpu_percent"] - 42.105) < 0.01
def test_vanishing_process_ignored(tmp_path):
    make_fixture.build(tmp_path); (tmp_path / "555").mkdir()                    # a directory with no status file, as if the process just exited
    assert 555 not in [p["pid"] for p in procmon.processes(str(tmp_path))]
