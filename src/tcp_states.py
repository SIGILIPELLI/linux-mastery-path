import socket, subprocess, time, threading
def states(port):
    out = subprocess.run(["lsof","-nP","-a","-iTCP:%d" % port],capture_output=True,text=True).stdout
    from collections import Counter
    return dict(Counter(l.split()[-1].strip("()") for l in out.splitlines()[1:]))
srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); srv.bind(("127.0.0.1", 0)); srv.listen(5)
port = srv.getsockname()[1]
print("1. after listen():", states(port))
cli = socket.create_connection(("127.0.0.1", port)); conn, _ = srv.accept()
print("2. after connect+accept:", states(port))
cli.sendall(b"hi"); print("   server received:", conn.recv(10))
cli.close(); time.sleep(0.2)
print("3. client closed first:", states(port))
conn.recv(10); conn.close(); time.sleep(0.3)
print("4. server closed too:", states(port))
# backlog and refused
s2 = socket.socket(); s2.bind(("127.0.0.1", 0)); p2 = s2.getsockname()[1]; s2.close()
try: socket.create_connection(("127.0.0.1", p2), timeout=2)
except Exception as e: print("5. connect to a closed port:", type(e).__name__, "-", e.strerror)
# address in use
try:
    s3 = socket.socket(); s3.bind(("127.0.0.1", port)); 
except Exception as e: print("6. bind to a port that is listening:", e.strerror)
# ephemeral port range
print("7. ephemeral port assigned to the client side example:", end=" ")
a = socket.create_connection(("127.0.0.1", port)); print(a.getsockname()[1] >= 1024); a.close()
srv.close()
