import os, time, fcntl, sys
p = "/private/tmp/claude-501/lx/io.tmp"; N = 256 * 1024 * 1024; chunk = b"x" * (1024 * 1024)
def mb_s(n, t): return n / t / 1e6
t = time.perf_counter()
fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
for _ in range(N // len(chunk)): os.write(fd, chunk)
t_write = time.perf_counter() - t
t = time.perf_counter(); os.fsync(fd); t_fsync = time.perf_counter() - t
t = time.perf_counter(); fcntl.fcntl(fd, fcntl.F_FULLFSYNC); t_full = time.perf_counter() - t
os.close(fd)
print(f"buffered write of 256 MB returned after {t_write*1000:.0f} ms ({mb_s(N, t_write):,.0f} MB/s apparent); fsync then took {t_fsync*1000:.0f} ms; F_FULLFSYNC {t_full*1000:.0f} ms")
def read(nocache):
    fd = os.open(p, os.O_RDONLY)
    if nocache: fcntl.fcntl(fd, fcntl.F_NOCACHE, 1)
    t = time.perf_counter(); n = 0
    while True:
        b = os.read(fd, 1024 * 1024)
        if not b: break
        n += len(b)
    dt = time.perf_counter() - t; os.close(fd); return mb_s(n, dt)
print(f"read with cache  : {read(False):,.0f} MB/s ; again: {read(False):,.0f} MB/s")
print(f"read with F_NOCACHE (bypass cache): {read(True):,.0f} MB/s ; again: {read(True):,.0f} MB/s")
os.remove(p)
