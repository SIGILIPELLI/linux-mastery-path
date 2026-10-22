import os, time, multiprocessing as mp, socket, subprocess, resource
def spin(n, q, nice):
    os.nice(nice); end=time.time()+3; c=0
    while time.time()<end: c+=1
    r=resource.getrusage(resource.RUSAGE_SELF); q.put((n, nice, round(r.ru_utime+r.ru_stime,2), c))
if __name__=="__main__":
    ncpu=os.cpu_count(); print("cpus:", ncpu, "| loadavg before:", tuple(round(x,2) for x in os.getloadavg()))
    q=mp.Queue(); procs=[]
    # oversubscribe: 2*ncpu busy processes, half nice 0 and half nice 15
    for i in range(ncpu*2): p=mp.Process(target=spin,args=(i,q,0 if i%2==0 else 15)); p.start(); procs.append(p)
    time.sleep(2.5); print("loadavg during (1-min):", round(os.getloadavg()[0],2))
    res=[q.get() for _ in procs]; [p.join() for p in procs]
    for lvl in (0,15):
        cpu=[r[2] for r in res if r[1]==lvl]; it=[r[3] for r in res if r[1]==lvl]
        print(f"nice {lvl:>2}: mean CPU seconds in 3s window = {sum(cpu)/len(cpu):.2f} ; mean loop iterations = {sum(it)/len(it):.2e}")
    print("== listen backlog")
    s=socket.socket(); s.bind(("127.0.0.1",0)); s.listen(1); port=s.getsockname()[1]    # never accept()
    ok=0; fail=[]
    cs=[]
    for i in range(8):
        c=socket.socket(); c.settimeout(1.0)
        try: c.connect(("127.0.0.1",port)); ok+=1; cs.append(c)
        except Exception as e: fail.append(type(e).__name__)
    print(f"listen(1), never accept(): {ok} of 8 connects completed; failures: {sorted(set(fail))} x{len(fail)}")
    print("accept queue size is capped by min(backlog, kernel limit); on Linux the limit is net.core.somaxconn (not run)")
