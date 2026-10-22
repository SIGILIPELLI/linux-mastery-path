"""Compare Debian package versions: [epoch:]upstream[-revision], per the algorithm in the Debian Policy Manual (section on version ordering).
'~' sorts before everything, even the end of the string. Letters sort before non-letters."""
import re

def _split(v):
    epoch = 0
    if ":" in v: e, v = v.split(":", 1); epoch = int(e)
    if "-" in v: up, rev = v.rsplit("-", 1)
    else: up, rev = v, "0"
    return epoch, up, rev

def _order(c):
    if c == "~": return -1
    if c.isdigit() or c == "": return 0
    if c.isalpha(): return ord(c)
    return ord(c) + 256

def _cmp_part(a, b):
    while a or b:
        # compare the non-digit prefix character by character
        na, nb = re.match(r"\D*", a).group(), re.match(r"\D*", b).group()
        a, b = a[len(na):], b[len(nb):]
        for i in range(max(len(na), len(nb))):
            ca = _order(na[i]) if i < len(na) else 0
            cb = _order(nb[i]) if i < len(nb) else 0
            if ca != cb: return -1 if ca < cb else 1
        da, db = re.match(r"\d*", a).group(), re.match(r"\d*", b).group()
        a, b = a[len(da):], b[len(db):]
        ia, ib = int(da or 0), int(db or 0)
        if ia != ib: return -1 if ia < ib else 1
    return 0

def compare(v1, v2):
    e1, u1, r1 = _split(v1); e2, u2, r2 = _split(v2)
    if e1 != e2: return -1 if e1 < e2 else 1
    return _cmp_part(u1, u2) or _cmp_part(r1, r2)
