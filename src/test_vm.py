from vmstat_triage import parse, triage
HDR = "procs -----------memory---------- ---swap-- -----io---- -system-- ------cpu-----\n r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa st\n"
HEALTHY = HDR + " 1  0      0 412000  90000 11000000    0    0     5    12  300  800  5  2 92  1  0\n 1  0      0 411000  90000 11000000    0    0     0    20  310  820  6  2 91  1  0\n"
CPU_BOUND = HDR + " 2  0      0 400000  90000 11000000    0    0     5    12  300  800  5  2 92  1  0\n 12 0      0 400000  90000 11000000    0    0     0    20 3100 9000 88 10  2  0  0\n 14 0      0 400000  90000 11000000    0    0     0    20 3100 9000 90  9  1  0  0\n"
IO_BOUND = HDR + " 1  0      0 400000  90000 11000000    0    0     5    12  300  800  5  2 92  1  0\n 1 14      0 400000  90000 11000000    0    0 90000 80000  900 2000  3  3 24 70  0\n 1 16      0 400000  90000 11000000    0    0 95000 85000  900 2100  2  3 20 75  0\n"
SWAPPING = HDR + " 1  0 100000 400000  90000 11000000    0    0     5    12  300  800  5  2 92  1  0\n 3  2 900000  20000   1000   100000 8000 6000 12000 9000 2000 3000 20 30 10 40  0\n"
def has(findings, needle): return any(needle in f for f in findings)
def test_healthy(): assert triage(parse(HEALTHY), 4) == ["no obvious saturation in this sample"]
def test_cpu_bound():
    f = triage(parse(CPU_BOUND), 4); assert has(f, "CPU saturation") and has(f, "CPU utilization")
def test_io_bound():
    f = triage(parse(IO_BOUND), 4); assert has(f, "I/O wait") and has(f, "uninterruptible") and not has(f, "CPU saturation")
def test_swapping(): assert has(triage(parse(SWAPPING), 4), "swapping")
def test_first_line_ignored(): assert triage(parse(CPU_BOUND.replace(" 12 0", " 1 0").replace(" 14 0", " 1 0")), 4)[0].startswith("CPU utilization")
def test_bad_columns():
    import pytest
    with pytest.raises(ValueError): parse("1 2 3\n")
