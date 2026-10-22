import os, time, mmap, resource, ctypes, sys, statistics as st
def rss_mb(): 
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / (1024*1024) if sys.platform == "darwin" else r / 1024
print("== page size / syscalls")
print("page size:", os.sysconf("SC_PAGE_SIZE"), "bytes")
def bench(f, n=200000):
    t=time.perf_counter(); 
    for _ in range(n): f()
    return (time.perf_counter()-t)/n*1e9
x = 5
print(f"python no-op call   : {bench(lambda: None):7.0f} ns/call")
print(f"os.getpid() (syscall): {bench(os.getpid):7.0f} ns/call")
fd = os.open("/dev/null", os.O_WRONLY)
print(f"os.write(/dev/null,1B): {bench(lambda: os.write(fd, b'x')):7.0f} ns/call")
libc = ctypes.CDLL(None); 
print(f"libc getppid via ctypes: {bench(libc.getppid):7.0f} ns/call")
print("== lazy allocation with mmap")
base = rss_mb()
m = mmap.mmap(-1, 512*1024*1024)               # ask for 512 MiB of anonymous memory
after_map = rss_mb()
for off in range(0, 128*1024*1024, 4096): m[off] = 1     # touch 128 MiB, one byte per page
after_touch = rss_mb()
print(f"peak RSS before mmap: {base:.0f} MB | after mmap(512MB): {after_map:.0f} MB | after touching 128MB: {after_touch:.0f} MB")
m.close()
print("== fork cost and copy-on-write")
big = bytearray(200*1024*1024)
t=time.perf_counter(); pid=os.fork()
if pid==0: os._exit(0)
os.waitpid(pid,0); print(f"fork of a process holding 200MB: {(time.perf_counter()-t)*1000:.1f} ms")
print("== fsync")
p="/private/tmp/claude-501/lx/fs.tmp"
def write(sync):
    t=time.perf_counter()
    with open(p,"wb") as f:
        for _ in range(20): f.write(b"x"*4096); f.flush(); 
        if sync: os.fsync(f.fileno())
    return (time.perf_counter()-t)*1000
print(f"20x4KB writes, no fsync: {write(False):.2f} ms ; with one fsync at the end: {write(True):.2f} ms")
t=time.perf_counter()
with open(p,"wb") as f:
    for _ in range(20): f.write(b"x"*4096); f.flush(); os.fsync(f.fileno())
print(f"20 writes each followed by fsync: {(time.perf_counter()-t)*1000:.2f} ms")
os.remove(p)
