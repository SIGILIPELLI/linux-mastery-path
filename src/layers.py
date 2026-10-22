"""OCI/Docker-style image layers as tar archives applied in order, with 'whiteout' files marking deletions (.wh.<name>) and
'.wh..wh..opq' marking an opaque directory. Demonstrates why deleting a file in a later layer does NOT shrink the image."""
import io, tarfile, posixpath

def make_layer(files=None, deletes=()):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as t:
        for path, data in (files or {}).items():
            ti = tarfile.TarInfo(path); ti.size = len(data); t.addfile(ti, io.BytesIO(data))
        for path in deletes:
            d, name = posixpath.split(path); ti = tarfile.TarInfo(posixpath.join(d, ".wh." + name)); ti.size = 0; t.addfile(ti, io.BytesIO(b""))
    return buf.getvalue()

def apply_layers(layers):
    fs = {}
    for blob in layers:
        with tarfile.open(fileobj=io.BytesIO(blob)) as t:
            for m in t.getmembers():
                d, name = posixpath.split(m.name)
                if name == ".wh..wh..opq":                                  # opaque dir: drop everything below it from lower layers
                    fs = {p: c for p, c in fs.items() if not p.startswith(d + "/")}
                elif name.startswith(".wh."):
                    target = posixpath.join(d, name[4:]); fs = {p: c for p, c in fs.items() if p != target and not p.startswith(target + "/")}
                elif m.isfile(): fs[m.name] = t.extractfile(m).read()
    return fs

def image_size(layers): return sum(len(b) for b in layers)
