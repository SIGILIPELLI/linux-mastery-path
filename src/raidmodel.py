"""RAID capacity/tolerance arithmetic and a parity (XOR) demonstration. Pure Python."""
import os, itertools
def usable(level, n, size_gb):
    if level == 0:  assert n >= 2; return n * size_gb, 0
    if level == 1:  assert n >= 2; return size_gb, n - 1
    if level == 5:  assert n >= 3; return (n - 1) * size_gb, 1
    if level == 6:  assert n >= 4; return (n - 2) * size_gb, 2
    if level == 10: assert n >= 4 and n % 2 == 0; return (n // 2) * size_gb, "1 per mirror pair (up to n/2, but 2 in the same pair is fatal)"
    raise ValueError(level)

def xor_blocks(*blocks):
    out = bytearray(len(blocks[0]))
    for b in blocks:
        for i, x in enumerate(b): out[i] ^= x
    return bytes(out)

def stripe_with_parity(data, blocksize, ndata):
    """Split data into stripes of ndata blocks; return list of (blocks, parity)."""
    pad = (-len(data)) % (blocksize * ndata); data += b"\0" * pad
    stripes = []
    for off in range(0, len(data), blocksize * ndata):
        blocks = [data[off + i * blocksize: off + (i + 1) * blocksize] for i in range(ndata)]
        stripes.append((blocks, xor_blocks(*blocks)))
    return stripes

def rebuild(stripe_blocks, parity, lost_index):
    survivors = [b for i, b in enumerate(stripe_blocks) if i != lost_index]
    return xor_blocks(parity, *survivors)

if __name__ == "__main__":
    print("level  disks  size  usable  failures tolerated")
    for lvl, n in [(0, 4), (1, 2), (5, 4), (6, 6), (10, 4)]:
        u, f = usable(lvl, n, 4000); print(f"{lvl:>5}  {n:>5}  4000  {u:>6}  {f}")
    msg = b"The quick brown fox jumps over the lazy dog."
    st = stripe_with_parity(msg, 8, 3)
    print("stripes:", len(st), "| first stripe blocks:", [b for b in st[0][0]], "| parity hex:", st[0][1].hex())
    blocks, parity = st[0]
    rec = rebuild(blocks, parity, 1)
    print("lost block 1 =", blocks[1], "| rebuilt from parity + survivors =", rec, "| equal:", rec == blocks[1])
    lost2 = xor_blocks(parity, blocks[2])
    print("two blocks lost (1 and 0), only one parity: cannot recover; XOR of parity^block2 gives", lost2.hex(), "= block0^block1:", lost2 == xor_blocks(blocks[0], blocks[1]))
    # write hole demo: update data block but crash before parity update
    new0 = b"XXXXXXXX"; stale_parity = parity
    rec_bad = rebuild([new0, blocks[1], blocks[2]], stale_parity, 1)
    print("write-hole: data updated, parity stale -> rebuilt block1 =", rec_bad, "(corrupt) vs true", blocks[1])
